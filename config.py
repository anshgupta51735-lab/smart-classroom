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
