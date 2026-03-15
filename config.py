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