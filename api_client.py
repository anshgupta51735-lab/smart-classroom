import requests
from datetime import datetime
from config import API_BASE_URL, ROOM_ID

def post_attendance(card_uid: str, action: str):
    payload = {
        "room_id": ROOM_ID,
        "card_uid": card_uid,
        "action": action.upper(),
        "timestamp": datetime.utcnow().isoformat()
    }
    r = requests.post(f"{API_BASE_URL}/api/attendance", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


def post_pir(occupied: bool):
    payload = {
        "room_id": ROOM_ID,
        "occupied": occupied,
        "timestamp": datetime.utcnow().isoformat()
    }
    r = requests.post(f"{API_BASE_URL}/api/pir", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


def post_relay_status(lights_on: bool, fans_on: bool, reason: str = ""):
    payload = {
        "room_id": ROOM_ID,
        "lights_on": lights_on,
        "fans_on": fans_on,
        "reason": reason
    }
    r = requests.post(f"{API_BASE_URL}/api/relay_status", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()
