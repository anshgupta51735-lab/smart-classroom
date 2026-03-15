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

