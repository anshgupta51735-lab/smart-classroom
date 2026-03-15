"""
arduino_agent.py
================
Smart Classroom System  -  Arduino Serial Agent
Reads sensor events from Arduino over USB serial, dispatches them
to handler modules, and forwards processed events to the FastAPI backend.

Dependencies:
    pip install pyserial requests opencv-python face_recognition python-dotenv

Usage:
    python arduino_agent.py

Environment variables  (.env file):
    SERIAL_PORT   = COM3          # Windows: COM3 / Linux: /dev/ttyUSB0 / macOS: /dev/cu.usbserial-*
    BAUD_RATE     = 9600
    API_BASE_URL  = http://127.0.0.1:8000
    API_KEY       = your_secret_api_key
"""

import os
import time
import logging
import threading

import serial
import serial.tools.list_ports
from dotenv import load_dotenv

from api_client import APIClient
from pir_sensor import PIRHandler
from rfid_reader import RFIDHandler
from fingerprint_reader import FingerprintHandler
from face_attendance import FaceAttendanceHandler

# ─────────────────────────────────────────────────────────────────────────────
# Load configuration from .env
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

SERIAL_PORT             = os.getenv("SERIAL_PORT", "AUTO")
BAUD_RATE               = int(os.getenv("BAUD_RATE", "9600"))
API_BASE_URL            = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_KEY                 = os.getenv("API_KEY", "changeme")
RECONNECT_DELAY_SECONDS = int(os.getenv("RECONNECT_DELAY", "5"))
SERIAL_TIMEOUT_SECONDS  = float(os.getenv("SERIAL_TIMEOUT", "2"))
MAX_LINE_LENGTH         = 256   # discard lines longer than this (noise guard)

# ─────────────────────────────────────────────────────────────────────────────
# Logging  -  writes to console AND arduino_agent.log
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("arduino_agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("arduino_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Agent class
# ─────────────────────────────────────────────────────────────────────────────
class ArduinoAgent:
    """
    Connects to an Arduino via USB serial and processes incoming
    sensor events in a resilient, auto-reconnecting loop.

    Supported serial message formats (sent by Arduino sketch):
        PIR:1          - motion detected
        PIR:0          - motion cleared
        RFID:A1B2C3D4  - RFID card UID scanned
        FINGER:7       - fingerprint matched to student ID 7
        FINGER:0       - no match / unknown finger
        RELAY:ON       - relay turned on (confirmation echo)
        RELAY:OFF      - relay turned off (confirmation echo)
        HEARTBEAT      - periodic Arduino alive signal (every 30 s)
        CMD:RELAY:ON   - Python can also SEND this to Arduino (not received)
    """

    def __init__(self) -> None:
        self.client = APIClient(base_url=API_BASE_URL, api_key=API_KEY)

        # Sensor handlers  -  all share the same APIClient
        self.pir         = PIRHandler(self.client)
        self.rfid        = RFIDHandler(self.client)
        self.fingerprint = FingerprintHandler(self.client)
        self.face        = FaceAttendanceHandler(self.client)

        self._serial: serial.Serial | None = None
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()   # protect concurrent serial writes

        # Prefix  →  handler callable
        self._dispatch_table: dict[str, callable] = {
            "PIR":       self.pir.handle,
            "RFID":      self.rfid.handle,
            "FINGER":    self.fingerprint.handle,
            "RELAY":     self._handle_relay_echo,
            "HEARTBEAT": self._handle_heartbeat,
        }

    # ─────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────
    def run(self) -> None:
        """Main entry point. Runs forever; auto-reconnects on serial failure."""
        log.info("Arduino agent starting | port=%s | baud=%d", SERIAL_PORT, BAUD_RATE)
        log.info("Backend: %s", API_BASE_URL)

        # Verify the backend is reachable before entering the serial loop
        self._check_backend_health()

        # Face recognition runs on the laptop camera in a background thread
        face_thread = threading.Thread(
            target=self.face.run_continuous,
            daemon=True,
            name="face-recognition",
        )
        face_thread.start()
        log.info("Face recognition thread started.")

        while not self._stop_event.is_set():
            try:
                self._connect()
                self._read_loop()
            except serial.SerialException as exc:
                log.error("Serial error: %s", exc)
                self._close_serial()
                log.info("Reconnecting in %d s…", RECONNECT_DELAY_SECONDS)
                time.sleep(RECONNECT_DELAY_SECONDS)
            except KeyboardInterrupt:
                log.info("Keyboard interrupt. Stopping agent.")
                self._stop_event.set()

        # Cleanup
        self._close_serial()
        self.face.stop()
        log.info("Arduino agent stopped cleanly.")

    def stop(self) -> None:
        """Signal the agent to stop after the current loop iteration."""
        self._stop_event.set()

    def send_command(self, command: str) -> bool:
        """
        Send a command string to the Arduino.
        Example:  agent.send_command("CMD:RELAY:ON")
        Returns True if sent, False if serial is not available.
        """
        if self._serial is None or not self._serial.is_open:
            log.warning("Cannot send command — serial not connected.")
            return False
        with self._write_lock:
            try:
                self._serial.write((command + "\n").encode("utf-8"))
                log.info("Sent command to Arduino: %r", command)
                return True
            except serial.SerialException as exc:
                log.error("Failed to send command %r: %s", command, exc)
                return False

    # ─────────────────────────────────────────
    # Connection management
    # ─────────────────────────────────────────
    def _connect(self) -> None:
        """Open the serial port. Auto-detects the port if SERIAL_PORT == 'AUTO'."""
        port = SERIAL_PORT

        if port.upper() == "AUTO":
            port = self._auto_detect_port()
            if port is None:
                raise serial.SerialException(
                    "No Arduino found. Plug in your Arduino and check drivers."
                )

        log.info("Opening serial port %s at %d baud…", port, BAUD_RATE)
        self._serial = serial.Serial(
            port=port,
            baudrate=BAUD_RATE,
            timeout=SERIAL_TIMEOUT_SECONDS,
            write_timeout=2,
        )
        # Arduino resets when serial opens; give it time to boot
        log.info("Waiting 2 s for Arduino to boot…")
        time.sleep(2)

        # Flush any startup noise from the Arduino
        self._serial.reset_input_buffer()
        log.info("Connected to %s. Listening for sensor events…", port)

    def _close_serial(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            log.info("Serial port closed.")
        self._serial = None

    @staticmethod
    def _auto_detect_port() -> str | None:
        """
        Scan all serial ports and return the first that looks like an Arduino.
        Matches against common Arduino USB-serial chip descriptions.
        """
        arduino_keywords = ["arduino", "ch340", "ch341", "cp2102", "cp2104", "ftdi"]
        ports = serial.tools.list_ports.comports()
        for port_info in ports:
            desc = (port_info.description or "").lower()
            mfr  = (port_info.manufacturer or "").lower()
            if any(k in desc or k in mfr for k in arduino_keywords):
                log.info(
                    "Auto-detected Arduino: %s (%s)",
                    port_info.device,
                    port_info.description,
                )
                return port_info.device
        log.warning(
            "Auto-detect found no Arduino. Available ports: %s",
            [p.device for p in ports] or "none",
        )
        return None

    # ─────────────────────────────────────────
    # Read loop
    # ─────────────────────────────────────────
    def _read_loop(self) -> None:
        """
        Block-reads lines from serial until disconnect or stop signal.
        Raises serial.SerialException on hardware disconnect so the outer
        loop can handle reconnection.
        """
        consecutive_empty = 0
        MAX_EMPTY = 100  # ~200 s of silence before we check connection

        while not self._stop_event.is_set():
            try:
                raw: bytes = self._serial.readline()
            except serial.SerialException:
                raise   # propagate to outer loop

            # readline() returns b'' on timeout — that is normal
            if not raw:
                consecutive_empty += 1
                if consecutive_empty >= MAX_EMPTY:
                    # Check the port is still physically open
                    if not self._serial.is_open:
                        raise serial.SerialException("Serial port closed unexpectedly.")
                    consecutive_empty = 0
                continue

            consecutive_empty = 0

            # Discard absurdly long lines (serial noise / buffer overrun)
            if len(raw) > MAX_LINE_LENGTH:
                log.warning("Oversized serial line (%d bytes) discarded.", len(raw))
                continue

            # Decode; replace undecodable bytes rather than crashing
            line = raw.decode("utf-8", errors="replace").strip()

            if line:
                self._dispatch(line)

    # ─────────────────────────────────────────
    # Dispatch
    # ─────────────────────────────────────────
    def _dispatch(self, line: str) -> None:
        """
        Parse a raw serial line and invoke the correct handler.

        Format:  PREFIX:VALUE  or just  HEARTBEAT
        """
        log.debug("Serial RX: %r", line)

        if ":" in line:
            prefix, _, value = line.partition(":")
        else:
            prefix = line
            value  = ""

        prefix = prefix.strip().upper()
        value  = value.strip()

        handler = self._dispatch_table.get(prefix)
        if handler:
            try:
                handler(value)
            except Exception as exc:
                # Never let a handler crash the agent
                log.error(
                    "Handler for '%s' raised: %s",
                    prefix, exc, exc_info=True,
                )
        else:
            log.debug("Unknown message prefix '%s' — ignoring.", prefix)

    # ─────────────────────────────────────────
    # Built-in simple handlers
    # ─────────────────────────────────────────
    def _handle_relay_echo(self, value: str) -> None:
        """Arduino echos back relay state changes as confirmation."""
        state = value.upper()
        log.info("Relay echo from Arduino: %s", state)
        self.client.post(
            "/devices/status",
            {"device": "relay", "state": state.lower()},
        )

    def _handle_heartbeat(self, _value: str) -> None:
        log.debug("Arduino heartbeat OK.")

    def _check_backend_health(self) -> None:
        """Warn if the FastAPI backend is not reachable at startup."""
        result = self.client.get("/health")
        if result is None:
            log.warning(
                "Backend at %s did not respond. "
                "Make sure FastAPI is running before sensor events arrive.",
                API_BASE_URL,
            )
        else:
            log.info("Backend health check OK: %s", result)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agent = ArduinoAgent()
    agent.run()