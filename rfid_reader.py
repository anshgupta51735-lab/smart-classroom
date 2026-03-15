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

