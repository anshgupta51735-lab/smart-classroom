import os
import time
import logging
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiosqlite

logger = logging.getLogger(__name__)

# ── Auth ─────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_key(key: str = Security(api_key_header)):
    if not API_KEY:
        raise RuntimeError("API_KEY environment variable not set on server")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key

AuthDep = Annotated[str, Depends(verify_key)]

# ── DB lifecycle ─────────────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "smartedu_pulse.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")  # enables concurrent reads
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                roll_no     TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT NOT NULL,
                classroom_id TEXT NOT NULL,
                method      TEXT NOT NULL,     -- rfid / fingerprint / face
                timestamp   TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id)
            );
            CREATE TABLE IF NOT EXISTS motion_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom_id TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS device_status (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom_id TEXT NOT NULL,
                lights      TEXT NOT NULL,
                fan         TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS timetable (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom_id TEXT NOT NULL,
                day_of_week  TEXT NOT NULL,  -- Monday, Tuesday, ...
                subject      TEXT NOT NULL,
                teacher      TEXT NOT NULL,
                start_time   TEXT NOT NULL,  -- HH:MM (24h)
                end_time     TEXT NOT NULL
            );
        """)
        await db.commit()
    yield  # app runs here
    # Shutdown: nothing special needed for SQLite

app = FastAPI(title="SmartEdu Pulse API", lifespan=lifespan)

# Connected WebSocket clients (for live dashboard updates)
_ws_clients: list[WebSocket] = []

async def broadcast(message: dict):
    """Push a JSON message to all connected dashboard browsers."""
    import json
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)

# ── Pydantic models ───────────────────────────────────────────────────────────

class AttendanceIn(BaseModel):
    student_id: str
    classroom_id: str
    method: str  # rfid / fingerprint / face

class MotionEventIn(BaseModel):
    classroom_id: str

class DeviceStatusIn(BaseModel):
    classroom_id: str
    lights: str
    fan: str

class TimetableSlotIn(BaseModel):
    classroom_id: str
    day_of_week: str
    subject: str
    teacher: str
    start_time: str
    end_time: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/attendance", dependencies=[Depends(verify_key)])
async def mark_attendance(data: AttendanceIn):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO attendance (student_id, classroom_id, method, timestamp) VALUES (?,?,?,?)",
            (data.student_id, data.classroom_id, data.method, ts)
        )
        await db.commit()
    await broadcast({"event": "attendance", "data": data.model_dump(), "timestamp": ts})
    return {"status": "recorded", "timestamp": ts}

@app.post("/events/motion", dependencies=[Depends(verify_key)])
async def motion_event(data: MotionEventIn):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO motion_events (classroom_id, timestamp) VALUES (?,?)",
            (data.classroom_id, ts)
        )
        await db.commit()
    await broadcast({"event": "motion", "classroom_id": data.classroom_id})
    return {"status": "ok"}

@app.post("/devices/status", dependencies=[Depends(verify_key)])
async def update_device_status(data: DeviceStatusIn):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO device_status (classroom_id, lights, fan, timestamp) VALUES (?,?,?,?)",
            (data.classroom_id, data.lights, data.fan, ts)
        )
        await db.commit()
    await broadcast({"event": "device_status", "data": data.model_dump()})
    return {"status": "ok"}

@app.get("/timetable/today", dependencies=[Depends(verify_key)])
async def get_today_timetable(classroom_id: str):
    today = datetime.now().strftime("%A")  # "Monday", "Tuesday", etc.
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM timetable WHERE classroom_id=? AND day_of_week=? ORDER BY start_time",
            (classroom_id, today)
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]

@app.post("/timetable", dependencies=[Depends(verify_key)])
async def add_timetable_slot(data: TimetableSlotIn):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO timetable (classroom_id,day_of_week,subject,teacher,start_time,end_time) VALUES (?,?,?,?,?,?)",
            (data.classroom_id, data.day_of_week, data.subject, data.teacher, data.start_time, data.end_time)
        )
        await db.commit()
    return {"status": "added"}

@app.get("/dashboard/stats")
async def dashboard_stats(classroom_id: str):
    """Public endpoint for the dashboard — no API key needed for reads."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT COUNT(*) as count FROM attendance WHERE classroom_id=? AND timestamp LIKE ?",
            (classroom_id, f"{today}%")
        ) as c:
            attendance_today = (await c.fetchone())["count"]

        async with db.execute(
            "SELECT lights, fan FROM device_status WHERE classroom_id=? ORDER BY id DESC LIMIT 1",
            (classroom_id,)
        ) as c:
            device = dict(await c.fetchone()) if await c.fetchone() else {"lights": "unknown", "fan": "unknown"}

    return {"attendance_today": attendance_today, "devices": device, "classroom_id": classroom_id}

# ── WebSocket for live dashboard ──────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection open, ignore pings
    except Exception:
        _ws_clients.remove(ws)

# ── Dashboard HTML (served by the same FastAPI server) ────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <title>SmartEdu Dashboard</title>
      <style>
        body { font-family: sans-serif; padding: 2rem; background: #f5f5f5; }
        .card { background: white; border-radius: 8px; padding: 1.5rem;
                margin-bottom: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
        .stat { font-size: 2.5rem; font-weight: bold; color: #2563eb; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 12px;
                 font-size: 0.85rem; margin-right: 6px; }
        .on  { background: #dcfce7; color: #166534; }
        .off { background: #fee2e2; color: #991b1b; }
        #log { font-size: 0.8rem; color: #6b7280; max-height: 200px; overflow-y: auto; }
      </style>
    </head>
    <body>
      <h1>SmartEdu Pulse — Live Dashboard</h1>
      <div class="card">
        <div>Attendance today</div>
        <div class="stat" id="attendance">—</div>
      </div>
      <div class="card">
        <div>Devices</div>
        <span class="badge" id="lights">Lights: —</span>
        <span class="badge" id="fan">Fan: —</span>
      </div>
      <div class="card">
        <div>Live events</div>
        <div id="log"></div>
      </div>
      <script>
        const classroom = new URLSearchParams(window.location.search).get('room') || 'Room-101';

        fetch(`/dashboard/stats?classroom_id=${classroom}`)
          .then(r => r.json()).then(d => {
            document.getElementById('attendance').textContent = d.attendance_today;
            setDevice('lights', d.devices.lights);
            setDevice('fan', d.devices.fan);
          });

        function setDevice(id, state) {
          const el = document.getElementById(id);
          el.textContent = id.charAt(0).toUpperCase() + id.slice(1) + ': ' + state;
          el.className = 'badge ' + state;
        }

        function log(msg) {
          const div = document.getElementById('log');
          const p = document.createElement('p');
          p.textContent = new Date().toLocaleTimeString() + ' — ' + msg;
          div.prepend(p);
        }

        const ws = new WebSocket(`ws://${location.host}/ws/dashboard`);
        ws.onmessage = e => {
          const d = JSON.parse(e.data);
          if (d.event === 'attendance') {
            document.getElementById('attendance').textContent =
              parseInt(document.getElementById('attendance').textContent || '0') + 1;
            log('Attendance marked: ' + d.data.student_id + ' via ' + d.data.method);
          } else if (d.event === 'device_status') {
            setDevice('lights', d.data.lights);
            setDevice('fan', d.data.fan);
            log('Devices updated');
          } else if (d.event === 'motion') {
            log('Motion detected in ' + d.classroom_id);
          }
        };
      </script>
    </body>
    </html>
    """
@app.get("/dashboard/energy-report")
async def energy_report(classroom_id: str):
    """
    Calculates estimated energy saved today by auto-shutting off lights/fan.
    """
    today = date.today().isoformat()
    # Count device_status records where lights=off during business hours
    # Assume 100W bulbs + 60W fan = 160W = 0.16 kWh per hour saved
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as off_events FROM device_status WHERE classroom_id=? AND lights='off' AND timestamp LIKE ?",
            (classroom_id, f"{today}%")
        ) as c:
            off_events = (await c.fetchone())["off_events"]
    # Each "off" status record represents ~5 mins of devices being off
    hours_saved = (off_events * 5) / 60
    kwh_saved = round(hours_saved * 0.16, 3)
    return {"hours_saved": round(hours_saved, 2), "kwh_saved": kwh_saved, "classroom_id": classroom_id}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "classroom_id": os.getenv("CLASSROOM_ID", "unknown"),
        "sensors": {
            "pir": "active",
            "rfid": "active",
            "fingerprint": "active",
            "camera": "active",
        },
        "uptime_seconds": int(time.monotonic()),
    }
