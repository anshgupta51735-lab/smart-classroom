<<<<<<< HEAD
import os
from dotenv import load_dotenv

load_dotenv()  # reads from .env file in the project root

class Config:
    # Server
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    API_KEY: str = os.getenv("API_KEY", "")

    # Identity
    CLASSROOM_ID: str = os.getenv("CLASSROOM_ID", "Room-101")

    # GPIO pins
    PIR_PIN: int = int(os.getenv("PIR_PIN", "17"))
    RELAY_LIGHT_PIN: int = int(os.getenv("RELAY_LIGHT_PIN", "27"))
    RELAY_FAN_PIN: int = int(os.getenv("RELAY_FAN_PIN", "22"))

    # Behaviour
    MOTION_TIMEOUT_SECONDS: int = int(os.getenv("MOTION_TIMEOUT_SECONDS", "300"))
    FACE_RECOGNITION_INTERVAL: int = int(os.getenv("FACE_RECOGNITION_INTERVAL", "30"))

    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise EnvironmentError(
                "API_KEY is not set. Create a .env file. See .env.example."
            )

config = Config()
=======
# config.py
API_BASE_URL = "http://127.0.0.1:8000"
ROOM_ID = "R101"

PIR_GPIO_PIN = 17
RELAY_LIGHTS_PIN = 27
RELAY_FANS_PIN = 22

# choose ONE:
USE_RFID = True         # False → use fingerprint
SCAN_COOLDOWN_SEC = 5   # ek hi card baar-baar count na ho

# Offline buffer file
EVENT_BUFFER_FILE = "offline_events.jsonl"
>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
