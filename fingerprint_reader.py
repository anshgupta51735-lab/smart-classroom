import logging
import threading
import time

log = logging.getLogger("fingerprint_reader")

# Minimum seconds before the same slot ID is accepted again.
SAME_FINGER_COOLDOWN_SECONDS = 4.0

# Maximum valid slot ID — depends on your sensor model.
# AS608 / R307 support IDs 1–127. Change if using a larger capacity sensor.
MAX_FINGER_ID = 127


class FingerprintHandler:
    """
    Handles FINGER:N messages received from Arduino.

    Args:
        api_client:  An APIClient instance for backend calls.
    """

    def __init__(self, api_client) -> None:
        self._client = api_client
        self._last_seen: dict[int, float] = {}   # finger_id → timestamp
        self._lock = threading.Lock()
        self._failed_attempts: int = 0

    # ─────────────────────────────────────────
    # Public interface  (called by ArduinoAgent)
    # ─────────────────────────────────────────
    def handle(self, value: str) -> None:
        """
        Entry point called by the agent dispatcher.
        value is the slot ID as a string, e.g. '7' for a match or '0' for no match.
        """
        try:
            finger_id = int(value)
        except ValueError:
            log.warning("FINGER received non-integer value %r — ignoring.", value)
            return

        if finger_id == 0:
            self._on_no_match()
            return

        if not (1 <= finger_id <= MAX_FINGER_ID):
            log.warning(
                "FINGER ID %d is outside valid range [1, %d] — ignoring.",
                finger_id, MAX_FINGER_ID,
            )
            return

        if self._is_duplicate(finger_id):
            log.debug("Fingerprint duplicate for ID %d within cooldown.", finger_id)
            return

        log.info("Fingerprint matched: slot ID=%d", finger_id)
        self._failed_attempts = 0
        self._record_read(finger_id)
        self._post_attendance(finger_id)

    # ─────────────────────────────────────────
    # No-match handling
    # ─────────────────────────────────────────
    def _on_no_match(self) -> None:
        self._failed_attempts += 1
        log.warning(
            "Fingerprint: no match. Consecutive failures: %d",
            self._failed_attempts,
        )
        # Alert backend after 3 consecutive failures (e.g. potential tailgating)
        if self._failed_attempts >= 3:
            log.warning("3+ consecutive fingerprint failures — posting security alert.")
            self._client.post(
                "/events/motion",   # reuse motion endpoint or add a dedicated one
                {
                    "event_type":          "fingerprint_failure",
                    "consecutive_failures": self._failed_attempts,
                },
            )
            self._failed_attempts = 0  # reset after posting

    # ─────────────────────────────────────────
    # De-duplication
    # ─────────────────────────────────────────
    def _is_duplicate(self, finger_id: int) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_seen.get(finger_id, 0.0)
            return (now - last) < SAME_FINGER_COOLDOWN_SECONDS

    def _record_read(self, finger_id: int) -> None:
        with self._lock:
            self._last_seen[finger_id] = time.monotonic()
            # Prune stale entries
            cutoff = time.monotonic() - SAME_FINGER_COOLDOWN_SECONDS * 10
            self._last_seen = {
                k: v for k, v in self._last_seen.items() if v > cutoff
            }

    # ─────────────────────────────────────────
    # Backend call
    # ─────────────────────────────────────────
    def _post_attendance(self, finger_id: int) -> None:
        """
        POST an attendance record.
        The backend maps fingerprint slot IDs to student records.
        """
        result = self._client.post(
            "/attendance",
            {
                "student_id": str(finger_id),
                "method":     "fingerprint",
                "finger_slot": finger_id,
            },
        )
        if result:
            student = result.get("student_name", f"Slot {finger_id}")
            log.info(
                "Attendance recorded for '%s' (fingerprint slot %d).",
                student, finger_id,
            )
        else:
            log.warning(
                "Failed to record fingerprint attendance for slot %d.",
                finger_id,
            )