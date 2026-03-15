from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sqlite3
import os
from lecture_detector import get_current_lecture

# Database path
DB_PATH = os.getenv("SMARTEDU_DB", "smartedu_pulse.db")

app = FastAPI(title="SmartEdu Pulse Backend")

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Database ----------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        batch TEXT,
        card_uid TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        action TEXT,
        timestamp TEXT
    );

    CREATE TABLE IF NOT EXISTS room_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT,
        event_type TEXT,
        payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


# ---------------- Models ----------------

class AttendanceEvent(BaseModel):
    card_uid: str
    action: str
    timestamp: Optional[datetime] = None


class PIREvent(BaseModel):
    room_id: str
    occupied: bool


class RelayStatus(BaseModel):
    room_id: str
    lights_on: bool
    fans_on: bool
    reason: Optional[str] = None


# ---------------- API Routes ----------------

@app.get("/")
def home():
    return {"status": "SmartEdu Pulse Backend Running"}


@app.post("/api/attendance")
def record_attendance(event: AttendanceEvent):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM students WHERE card_uid=?",
        (event.card_uid,)
    )

    student = cur.fetchone()

    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not registered")

    student_id = student["id"]
    ts = event.timestamp or datetime.utcnow()

    cur.execute(
        "INSERT INTO attendance(student_id,action,timestamp) VALUES(?,?,?)",
        (student_id, event.action.upper(), ts)
    )

    conn.commit()
    conn.close()

    return {"status": "attendance recorded", "student_id": student_id}


@app.post("/api/pir")
def record_pir(event: PIREvent):

    conn = get_conn()
    cur = conn.cursor()

    payload = f"occupied={event.occupied}"

    cur.execute(
        "INSERT INTO room_events(room_id,event_type,payload) VALUES(?,?,?)",
        (event.room_id, "PIR", payload)
    )

    conn.commit()
    conn.close()

    return {"status": "pir recorded"}


@app.post("/api/relay_status")
def relay_status(status: RelayStatus):

    conn = get_conn()
    cur = conn.cursor()

    payload = f"lights_on={status.lights_on};fans_on={status.fans_on};reason={status.reason}"

    cur.execute(
        "INSERT INTO room_events(room_id,event_type,payload) VALUES(?,?,?)",
        (status.room_id, "RELAY", payload)
    )

    conn.commit()
    conn.close()

    return {"status": "relay updated"}


# ---------------- Dashboard APIs ----------------

@app.get("/api/attendance/latest")
def latest_attendance():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id,a.timestamp,a.action,
               s.name
        FROM attendance a
        LEFT JOIN students s ON a.student_id=s.id
        ORDER BY a.timestamp DESC
        LIMIT 50
    """)

    rows = [dict(r) for r in cur.fetchall()]

    conn.close()

    return rows


@app.get("/api/rooms/status")
def room_status():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT room_id,event_type,payload,created_at
        FROM room_events
        ORDER BY created_at DESC
        LIMIT 20
    """)

    rows = [dict(r) for r in cur.fetchall()]

    conn.close()

    return rows
from lecture_detector import get_current_lecture


@app.get("/api/current_lecture")

def current_lecture():

    lecture = get_current_lecture()

    return {"current_lecture":lecture}
