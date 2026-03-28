from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from livingroomcam.database import Database


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatabaseTests(unittest.TestCase):
    def test_rename_updates_person_and_visits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "livingroomcam.sqlite3")
            timestamp = now()
            db.upsert_person("unknown_aaaaaa", "unknown_aaaaaa", "unknown", timestamp)
            db.start_visit(
                visit_id="visit_1",
                display_label="unknown_aaaaaa",
                camera_name="living-room-cam-1",
                started_at=timestamp,
                enter_reason="zone-crossing",
                person_id="unknown_aaaaaa",
            )
            db.rename_person("unknown_aaaaaa", "Alice", now())
            people = db.people()
            visits = db.visits()
            self.assertEqual(people[0]["display_name"], "Alice")
            self.assertEqual(visits[0]["display_label"], "Alice")


if __name__ == "__main__":
    unittest.main()
