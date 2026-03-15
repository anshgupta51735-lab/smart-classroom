<<<<<<< HEAD
import logging
from enum import Enum
from config import config

logger = logging.getLogger(__name__)

class RelayState(Enum):
    ON = "on"
    OFF = "off"

class RelayController:
    """
    Controls a relay board. Supports active-HIGH and active-LOW relays.
    active_low=True means GPIO.LOW turns the relay ON (most relay boards work this way).
    """

    def __init__(self, light_pin: int = None, fan_pin: int = None, active_low: bool = True):
        self.light_pin = light_pin or config.RELAY_LIGHT_PIN
        self.fan_pin = fan_pin or config.RELAY_FAN_PIN
        self._active_low = active_low
        self._light_state = RelayState.OFF
        self._fan_state = RelayState.OFF
        self._gpio = None

    def setup(self):
        """Initialise GPIO. Called once at startup."""
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            for pin in [self.light_pin, self.fan_pin]:
                GPIO.setup(pin, GPIO.OUT)
                # Set relays to OFF at startup
                GPIO.output(pin, GPIO.HIGH if self._active_low else GPIO.LOW)
            logger.info("Relay controller initialised")
        except ImportError:
            logger.warning("RPi.GPIO not available — relay running in mock mode")

    def _set_relay(self, pin: int, turn_on: bool):
        if not self._gpio:
            logger.info(f"[MOCK] Pin {pin} → {'ON' if turn_on else 'OFF'}")
            return
        if self._active_low:
            self._gpio.output(pin, self._gpio.LOW if turn_on else self._gpio.HIGH)
        else:
            self._gpio.output(pin, self._gpio.HIGH if turn_on else self._gpio.LOW)

    def lights_on(self):
        self._set_relay(self.light_pin, True)
        self._light_state = RelayState.ON
        logger.info("Lights ON")

    def lights_off(self):
        self._set_relay(self.light_pin, False)
        self._light_state = RelayState.OFF
        logger.info("Lights OFF")

    def fan_on(self):
        self._set_relay(self.fan_pin, True)
        self._fan_state = RelayState.ON
        logger.info("Fan ON")

    def fan_off(self):
        self._set_relay(self.fan_pin, False)
        self._fan_state = RelayState.OFF
        logger.info("Fan OFF")

    @property
    def status(self) -> dict:
        return {
            "lights": self._light_state.value,
            "fan": self._fan_state.value,
        }

    def cleanup(self):
        """Turn everything off and release GPIO."""
        self.lights_off()
        self.fan_off()
        if self._gpio:
            self._gpio.cleanup([self.light_pin, self.fan_pin])
        logger.info("Relay controller cleaned up")
=======
# relay_controller.py
"""
Smart relay controller
- Light/Fan ke GPIO pins ko ON/OFF karta hai.
"""

import RPi.GPIO as GPIO
from config import RELAY_LIGHTS_PIN, RELAY_FANS_PIN

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_LIGHTS_PIN, GPIO.OUT)
GPIO.setup(RELAY_FANS_PIN, GPIO.OUT)


def set_relays(lights_on: bool, fans_on: bool):
    # NOTE: active-low relays ho sakte hain; wiring ke hisaab se invert karein
    GPIO.output(RELAY_LIGHTS_PIN, GPIO.HIGH if lights_on else GPIO.LOW)
    GPIO.output(RELAY_FANS_PIN, GPIO.HIGH if fans_on else GPIO.LOW)

>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
