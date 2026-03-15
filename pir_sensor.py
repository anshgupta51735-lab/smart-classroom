<<<<<<< HEAD
import logging
import threading
import time
from typing import Callable

log = logging.getLogger("pir_sensor")

# Minimum seconds between motion events sent to the backend.
# PIR sensors often send multiple triggers on a single motion — this
# prevents flooding the API.
DEBOUNCE_SECONDS = 3.0

# After this many seconds with no motion, send a "room empty" event.
IDLE_TIMEOUT_SECONDS = 120


class PIRHandler:
    def __init__(self, api_client, send_command: Callable | None = None) -> None:
        self._client       = api_client
        self._send_command = send_command

        self._last_motion_time: float = 0.0
        self._is_occupied: bool = False
        self._debounce_lock = threading.Lock()

        # Timer that fires when the room has been idle too long
        self._idle_timer: threading.Timer | None = None

    # ─────────────────────────────────────────
    # Public interface  (called by ArduinoAgent)
    # ─────────────────────────────────────────
    def handle(self, value: str) -> None:
        """
        Entry point called by the agent dispatcher.
        value is '1' (motion detected) or '0' (motion cleared).
        """
        if value == "1":
            self._on_motion_detected()
        elif value == "0":
            self._on_motion_cleared()
        else:
            log.warning("PIR received unexpected value: %r", value)

    @property
    def is_occupied(self) -> bool:
        """True if the room is currently considered occupied."""
        return self._is_occupied

    # ─────────────────────────────────────────
    # Internal event logic
    # ─────────────────────────────────────────
    def _on_motion_detected(self) -> None:
        now = time.monotonic()

        with self._debounce_lock:
            elapsed = now - self._last_motion_time
            if elapsed < DEBOUNCE_SECONDS:
                log.debug(
                    "PIR debounce: ignoring motion event (%.1f s since last).", elapsed
                )
                return
            self._last_motion_time = now

        log.info("Motion detected in classroom.")

        # Cancel any pending idle timer
        self._cancel_idle_timer()

        was_occupied = self._is_occupied
        self._is_occupied = True

        # Only POST and turn on lights on the first detection after idle
        if not was_occupied:
            self._post_motion_event(detected=True)
            self._turn_relay_on()

        # Restart the idle timer
        self._start_idle_timer()

    def _on_motion_cleared(self) -> None:
        """
        Arduino sent PIR:0. Some PIR modules send this explicitly;
        others only send PIR:1. The idle timer handles the silent case.
        """
        log.info("PIR cleared signal received.")
        self._cancel_idle_timer()
        self._set_room_empty()

    def _idle_timeout_reached(self) -> None:
        """Called by the timer when no motion has been detected for IDLE_TIMEOUT_SECONDS."""
        log.info(
            "No motion for %d s — marking room as empty.", IDLE_TIMEOUT_SECONDS
        )
        self._set_room_empty()

    def _set_room_empty(self) -> None:
        if self._is_occupied:
            self._is_occupied = False
            self._post_motion_event(detected=False)
            self._turn_relay_off()

    # ─────────────────────────────────────────
    # Backend calls
    # ─────────────────────────────────────────
    def _post_motion_event(self, detected: bool) -> None:
        result = self._client.post(
            "/events/motion",
            {
                "motion_detected": detected,
                "sensor": "pir",
            },
        )
        if result:
            log.info(
                "Motion event posted: detected=%s  response=%r",
                detected, result,
            )
        else:
            log.warning("Failed to post motion event to backend.")

    # ─────────────────────────────────────────
    # Relay control (via Arduino serial command)
    # ─────────────────────────────────────────
    def _turn_relay_on(self) -> None:
        if self._send_command:
            self._send_command("CMD:RELAY:ON")
            log.info("Relay ON command sent (motion detected).")

    def _turn_relay_off(self) -> None:
        if self._send_command:
            self._send_command("CMD:RELAY:OFF")
            log.info("Relay OFF command sent (room idle).")

    # ─────────────────────────────────────────
    # Idle timer helpers
    # ─────────────────────────────────────────
    def _start_idle_timer(self) -> None:
        self._idle_timer = threading.Timer(
            IDLE_TIMEOUT_SECONDS, self._idle_timeout_reached
        )
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _cancel_idle_timer(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
=======
# pir_sensor.py
import RPi.GPIO as GPIO
import time

from config import PIR_GPIO_PIN

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_GPIO_PIN, GPIO.IN)

def read_pir():
    """True = motion/occupied, False = no motion."""
    return GPIO.input(PIR_GPIO_PIN) == GPIO.HIGH

def watch_pir(callback, poll_interval=0.5):
    """
    PIR state watcher.
    callback(occupied: bool) jab state change hota hai.
    """
    last_state = None
    try:
        while True:
            occupied = read_pir()
            if occupied != last_state:
                last_state = occupied
                callback(occupied)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        GPIO.cleanup()

>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
