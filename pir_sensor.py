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

