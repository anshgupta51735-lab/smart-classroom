<<<<<<< HEAD
import logging
import re
import time
import threading

log = logging.getLogger("rfid_reader")

# Minimum seconds between accepting the same UID twice.
# Prevents double-counting when a card is held near the reader.
SAME_CARD_COOLDOWN_SECONDS = 5.0

# RFID UIDs are 4–10 hex bytes (8–20 hex chars).
_UID_PATTERN = re.compile(r"^[0-9A-Fa-f]{4,20}$")


class RFIDHandler:
    """
    Handles RFID:XXXXXXXX messages received from Arduino.

    Args:
        api_client:  An APIClient instance for backend calls.
    """

    def __init__(self, api_client) -> None:
        self._client = api_client
        self._last_seen: dict[str, float] = {}   # uid → last accepted timestamp
        self._lock = threading.Lock()

    # ─────────────────────────────────────────
    # Public interface  (called by ArduinoAgent)
    # ─────────────────────────────────────────
    def handle(self, value: str) -> None:
        """
        Entry point called by the agent dispatcher.
        value is the raw UID string, e.g. 'A1B2C3D4'.
        """
        uid = value.strip().upper()

        if not uid:
            log.warning("RFID received empty UID — ignoring.")
            return

        if not self._is_valid_uid(uid):
            log.warning("RFID received malformed UID %r — ignoring.", uid)
            return

        if self._is_duplicate(uid):
            log.debug("RFID duplicate scan for UID %s within cooldown window.", uid)
            return

        log.info("RFID card scanned: UID=%s", uid)
        self._record_scan(uid)
        self._post_attendance(uid)

    # ─────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────
    @staticmethod
    def _is_valid_uid(uid: str) -> bool:
        """Accept only hex strings of the correct length for RFID UIDs."""
        return bool(_UID_PATTERN.match(uid))

    # ─────────────────────────────────────────
    # De-duplication
    # ─────────────────────────────────────────
    def _is_duplicate(self, uid: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_seen.get(uid, 0.0)
            return (now - last) < SAME_CARD_COOLDOWN_SECONDS

    def _record_scan(self, uid: str) -> None:
        with self._lock:
            self._last_seen[uid] = time.monotonic()
            # Prune old entries to prevent unbounded growth
            cutoff = time.monotonic() - SAME_CARD_COOLDOWN_SECONDS * 10
            self._last_seen = {
                k: v for k, v in self._last_seen.items() if v > cutoff
            }

    # ─────────────────────────────────────────
    # Backend call
    # ─────────────────────────────────────────
    def _post_attendance(self, uid: str) -> None:
        """
        POST an attendance record.
        The backend is responsible for looking up which student owns this UID.
        """
        result = self._client.post(
            "/attendance",
            {
                "student_id": uid,
                "method":     "rfid",
                "raw_uid":    uid,
            },
        )
        if result:
            student = result.get("student_name", "Unknown")
            log.info("Attendance recorded for '%s' (UID=%s).", student, uid)
        else:
            log.warning(
                "Failed to record RFID attendance for UID %s. "
                "Will NOT retry — card may be scanned again.",
                uid,
            )
=======
# rfid_reader.py
"""
RFID reader wrapper.
Real hardware ke liye MFRC522 / SimpleMFRC522 library use karein.
Yahan interface simple rakha gaya hai for integration.
"""

import time

class RFIDReader:
    def __init__(self):
        # yahan hardware init karein (GPIO/SPI)
        # e.g. self.reader = SimpleMFRC522()
        pass

    def read_card_uid(self) -> str:
        """
        Blocking call: waits for card, returns UID string.
        Demo ke liye yeh function stub hai; real code me
        library call se UID read karenge.
        """
        # Example pseudo:
        # id, text = self.reader.read()
        # return str(id)
        raise NotImplementedError("Integrate with specific RFID library on Pi")


if __name__ == "__main__":
    r = RFIDReader()
    while True:
        try:
            uid = r.read_card_uid()
            print("Card UID:", uid)
            time.sleep(1)
        except KeyboardInterrupt:
            break

>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
