<<<<<<< HEAD
import logging
import signal
import time
import threading

from config import config
from hardware.pir_sensor import PIRSensor
from hardware.rfid_reader import RFIDReader
from hardware.fingerprint_reader import FingerprintReader
from hardware.face_attendance import FaceAttendance
from hardware.relay_controller import RelayController
from api_client import APIClient
from lecture_detector import LectureDetector
from energy_utils import EnergyManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pi_agent")

class SmartClassroomAgent:
    """
    Main agent for the Smart Classroom System.
    Coordinates all hardware and API communication using event callbacks.
    Each sensor runs on its own background thread.
    The main thread runs a periodic maintenance loop (energy management, timetable refresh).
    """

    def __init__(self):
        self._running = False
        self.classroom_id = config.CLASSROOM_ID

        # Initialise subsystems (dependency injection — easy to test/mock)
        self.api = APIClient()
        self.relay = RelayController()
        self.detector = LectureDetector(self.api)
        self.energy = EnergyManager(self.relay, self.detector)

        # Hardware drivers (each gets a callback to call when it detects something)
        self.pir = PIRSensor(on_motion=self._on_motion)
        self.rfid = RFIDReader(on_card_read=self._on_rfid)
        self.fingerprint = FingerprintReader(on_match=self._on_fingerprint)
        self.face = FaceAttendance(
            on_recognised=self._on_face,
            interval=config.FACE_RECOGNITION_INTERVAL
        )

    # ── Event handlers (called from hardware threads) ──────────────────────

    def _on_motion(self):
        logger.info("[EVENT] Motion detected")
        self.energy.on_motion_detected()
        self.api.post_motion_event(self.classroom_id)

    def _on_rfid(self, card_id: str):
        logger.info(f"[EVENT] RFID scan: {card_id}")
        self.api.post_attendance(card_id, "rfid", self.classroom_id)

    def _on_fingerprint(self, finger_id: int):
        logger.info(f"[EVENT] Fingerprint match: {finger_id}")
        self.api.post_attendance(str(finger_id), "fingerprint", self.classroom_id)

    def _on_face(self, name: str):
        logger.info(f"[EVENT] Face recognised: {name}")
        self.api.post_attendance(name, "face", self.classroom_id)

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self):
        logger.info(f"Starting Smart Classroom Agent — Room: {self.classroom_id}")
        config.validate()  # fail fast if config is missing

        self.relay.setup()
        self.detector.refresh_timetable()

        # Start all hardware threads
        self.pir.start()
        self.rfid.start()
        self.fingerprint.start()
        self.face.start()

        self._running = True
        logger.info("All systems started — entering main loop")
        self._main_loop()

    def _main_loop(self):
        """
        Main thread: runs periodic tasks.
        Hardware events are handled by background threads.
        """
        last_timetable_refresh = 0
        last_status_post = 0

        while self._running:
            now = time.monotonic()

            # Refresh timetable every hour
            if now - last_timetable_refresh > 3600:
                self.detector.refresh_timetable()
                last_timetable_refresh = now

            # Post device status every 5 minutes
            if now - last_status_post > 300:
                status = self.relay.status
                self.api.post_device_status(self.classroom_id, **status)
                last_status_post = now

            # Energy management tick every 60 seconds
            self.energy.tick()

            time.sleep(60)

    def stop(self):
        logger.info("Shutting down Smart Classroom Agent...")
        self._running = False
        self.pir.stop()
        self.rfid.stop()
        self.fingerprint.stop()
        self.face.stop()
        self.relay.cleanup()
        logger.info("Shutdown complete")


def main():
    agent = SmartClassroomAgent()

    # Graceful shutdown on Ctrl+C or kill signal
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig} — shutting down")
        agent.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.start()


if __name__ == "__main__":
    main()
=======
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

>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
