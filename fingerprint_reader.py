# fingerprint_reader.py
"""
pyfingerprint / vendor lib use karke R307 integrate karein.
Interface: read_template_id() → unique string/id.
"""

class FingerprintReader:
    def __init__(self):
        # serial init etc.
        pass

    def read_template_id(self) -> str:
        raise NotImplementedError("Integrate R307 library on real Pi")