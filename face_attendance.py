import logging
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("face_attendance")

# Folder containing enrolled student face images
KNOWN_FACES_DIR = Path(os.getenv("KNOWN_FACES_DIR", "known_faces"))

# Seconds between successive attendance POSTs for the SAME person
RECOGNITION_COOLDOWN_SECONDS = float(os.getenv("FACE_COOLDOWN", "30"))

# Camera index (0 = built-in webcam, 1 = external USB camera)
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

# How often the face loop checks for new frames (seconds)
FRAME_INTERVAL = 0.2


class FaceAttendanceHandler:
    """
    Runs a continuous face recognition loop in a background thread.
    Calls POST /attendance when a known face is identified.

    Args:
        api_client:  An APIClient instance for backend calls.
    """

    def __init__(self, api_client) -> None:
        self._client = api_client
        self._stop_event = threading.Event()
        self._last_seen: dict[str, float] = {}   # student_id → timestamp
        self._known_encodings: list = []
        self._known_ids: list[str] = []
        self._encodings_loaded = False

    # ─────────────────────────────────────────
    # Lifecycle  (called by ArduinoAgent)
    # ─────────────────────────────────────────
    def run_continuous(self) -> None:
        """
        Entry point for the background thread.
        Loads known faces, then loops until stop() is called.
        """
        # Lazy import — so the agent still starts if face_recognition is not installed
        try:
            import cv2
            import face_recognition as fr
        except ImportError:
            log.warning(
                "face_recognition or opencv-python not installed. "
                "Face attendance disabled. "
                "Run: pip install opencv-python face_recognition"
            )
            return

        self._load_known_faces(fr)
        if not self._known_encodings:
            log.warning(
                "No enrolled faces found in '%s'. "
                "Add student JPEGs before starting.",
                KNOWN_FACES_DIR,
            )
            return

        log.info(
            "Face recognition started. Enrolled students: %d. Camera index: %d",
            len(self._known_encodings), CAMERA_INDEX,
        )

        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            log.error(
                "Could not open camera (index %d). "
                "Check CAMERA_INDEX in .env.",
                CAMERA_INDEX,
            )
            return

        try:
            self._recognition_loop(cap, fr)
        finally:
            cap.release()
            log.info("Camera released. Face recognition stopped.")

    def stop(self) -> None:
        self._stop_event.set()

    # ─────────────────────────────────────────
    # Face loading
    # ─────────────────────────────────────────
    def _load_known_faces(self, fr) -> None:
        """
        Load all JPEG/PNG files from KNOWN_FACES_DIR.
        File naming convention:  STUDENT_ID_Anything.jpg
        e.g.  STU042_Ansh_Gupta.jpg  → student_id = 'STU042'
        """
        if not KNOWN_FACES_DIR.exists():
            log.warning(
                "known_faces/ directory not found. "
                "Create it and add student photos."
            )
            return

        for img_path in sorted(KNOWN_FACES_DIR.iterdir()):
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue

            student_id = img_path.stem.split("_")[0]

            try:
                image = fr.load_image_file(str(img_path))
                encodings = fr.face_encodings(image)
                if not encodings:
                    log.warning(
                        "No face detected in %s — skipping.", img_path.name
                    )
                    continue
                self._known_encodings.append(encodings[0])
                self._known_ids.append(student_id)
                log.info("Enrolled face: %s (%s)", student_id, img_path.name)
            except Exception as exc:
                log.error("Failed to load %s: %s", img_path.name, exc)

        log.info(
            "Face enrolment complete: %d / %d files loaded successfully.",
            len(self._known_encodings),
            sum(1 for p in KNOWN_FACES_DIR.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}),
        )
        self._encodings_loaded = True

    # ─────────────────────────────────────────
    # Recognition loop
    # ─────────────────────────────────────────
    def _recognition_loop(self, cap, fr) -> None:
        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                log.warning("Camera frame capture failed. Retrying…")
                time.sleep(1)
                continue

            # Downsample for speed (process at 1/4 resolution, match at full)
            small = frame[:, :, ::-1]   # BGR → RGB  (face_recognition uses RGB)

            face_locations = fr.face_locations(small)
            if not face_locations:
                time.sleep(FRAME_INTERVAL)
                continue

            face_encodings_in_frame = fr.face_encodings(small, face_locations)

            for encoding in face_encodings_in_frame:
                matches = fr.compare_faces(
                    self._known_encodings, encoding, tolerance=0.55
                )
                distances = fr.face_distance(self._known_encodings, encoding)

                if not any(matches):
                    log.debug("Unknown face detected.")
                    continue

                # Pick the closest match
                best_idx = int(distances.argmin())
                if not matches[best_idx]:
                    continue

                student_id = self._known_ids[best_idx]
                self._handle_recognised_face(student_id)

            time.sleep(FRAME_INTERVAL)

    def _handle_recognised_face(self, student_id: str) -> None:
        # Cooldown check — don't re-mark attendance every frame
        now = time.monotonic()
        last = self._last_seen.get(student_id, 0.0)
        if (now - last) < RECOGNITION_COOLDOWN_SECONDS:
            return

        self._last_seen[student_id] = now
        log.info("Face recognised: student_id=%s", student_id)

        result = self._client.post(
            "/attendance",
            {
                "student_id": student_id,
                "method":     "face_recognition",
            },
        )
        if result:
            log.info(
                "Face attendance recorded for %s.",
                result.get("student_name", student_id),
            )
        else:
            log.warning(
                "Backend call failed for face attendance of %s.", student_id
            )