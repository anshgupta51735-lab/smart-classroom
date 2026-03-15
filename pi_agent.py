# pi-node/pi_agent.py
"""
Pi main agent:
- RFID scan → attendance IN/OUT
- PIR motion → occupancy signal backend ko
- Occupancy < 20% → lights/fans OFF (relay)
"""

import threading
import time
from datetime import datetime
from rfid_reader import RFIDReader
from pir_sensor import watch_pir
from relay_controller import set_relays
from api_client import post_attendance, post_pir, post_relay_status
from config import SCAN_COOLDOWN_SEC as SCAN_COOLDOWN_SECONDS

# State variables (simple in-memory)
last_seen_card = {}
room_occupied = False

rfid_reader = RFIDReader()


def handle_rfid():
    while True:
        try:
            uid = rfid_reader.read_card_uid()
            now = datetime.utcnow()
            last_time = last_seen_card.get(uid)
            if last_time and (now - last_time).total_seconds() < SCAN_COOLDOWN_SECONDS:
                continue  # spam avoid karein

            last_seen_card[uid] = now
            # Simple rule: first scan = IN, next = OUT (toggle)
            action = "IN"
            if uid in last_seen_card and last_time:
                # alternate IN/OUT; real system me proper state tracking karein
                action = "OUT" if (int(now.timestamp()) // 2) % 2 == 0 else "IN"

            try:
                post_attendance(uid, action)
                print(f"[RFID] UID {uid} → {action}")
            except Exception as e:
                print("Error sending attendance:", e)
        except Exception as e:
            print("RFID read error:", e)
            time.sleep(1)


def handle_pir_event(occupied: bool):
    global room_occupied
    room_occupied = occupied
    try:
        post_pir(occupied)
    except Exception as e:
        print("Error sending PIR:", e)
    # Local control logic: if not occupied → turn everything OFF
    if not occupied:
        set_relays(False, False)
        try:
            post_relay_status(False, False, reason="Auto-off: no motion")
        except Exception as e:
            print("Error sending relay status:", e)
    else:
        # Occupied → you may choose to auto ON or keep manual
        set_relays(True, True)
        try:
            post_relay_status(True, True, reason="Auto-on: motion detected")
        except Exception as e:
            print("Error sending relay status:", e)


def handle_pir():
    watch_pir(handle_pir_event)


if __name__ == "__main__":
    t1 = threading.Thread(target=handle_rfid, daemon=True)
    t2 = threading.Thread(target=handle_pir, daemon=True)
    t1.start()
    t2.start()
    print("Pi agent running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

