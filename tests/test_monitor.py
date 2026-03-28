from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from livingroomcam.config import ServerConfig
from livingroomcam.database import Database
from livingroomcam.monitor import RoomMonitor, utc_now
from livingroomcam.types import FaceDetection, FrameAnalysis


class FakeBackend:
    name = "fake"

    def __init__(self) -> None:
        self._result = FrameAnalysis(
            width=1280,
            height=720,
            detections=[
                FaceDetection(
                    bbox=(320, 200, 200, 200),
                    quality=0.9,
                    embedding=[1.0, 0.0, 0.0, 0.0],
                    crop_jpeg=b"\xff\xd8\xff\xd9",
                )
            ],
            backend_name="fake",
        )

    def analyze_frame(self, jpeg_bytes: bytes) -> FrameAnalysis:
        return self._result


class MonitorTests(unittest.TestCase):
    def test_monitor_creates_unknown_person_after_enough_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = ServerConfig(
                db_path=root / "data.sqlite3",
                frame_store_dir=root / "frames",
                face_store_dir=root / "faces",
                static_dir=root,
                min_samples_to_classify=3,
            )
            database = Database(config.db_path)
            monitor = RoomMonitor(config, database, FakeBackend())
            for _ in range(3):
                monitor.process_frame(b"\xff\xd8\xff\xd9")
            people = database.people()
            visits = database.visits()
            self.assertEqual(len(people), 1)
            self.assertEqual(people[0]["status"], "unknown")
            self.assertEqual(len(visits), 1)


if __name__ == "__main__":
    unittest.main()
