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