from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading


SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS visits (
    id TEXT PRIMARY KEY,
    person_id TEXT,
    display_label TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds REAL,
    status TEXT NOT NULL,
    enter_reason TEXT,
    leave_reason TEXT,
    best_snapshot_path TEXT,
    camera_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS face_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    visit_id TEXT,
    track_id TEXT,
    captured_at TEXT NOT NULL,
    quality REAL NOT NULL,
    image_path TEXT,
    embedding_json TEXT,
    width INTEGER,
    height INTEGER
);

CREATE TABLE IF NOT EXISTS camera_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    person_id TEXT,
    visit_id TEXT,
    track_id TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS latest_frame (
    camera_name TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    frame_path TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    detection_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS camera_config (
    camera_name TEXT PRIMARY KEY,
    entry_zone_json TEXT NOT NULL,
    occupancy_zone_json TEXT NOT NULL,
    exit_zone_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._conn:
            self._conn.executescript(SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")

    def upsert_person(self, person_id: str, display_name: str, status: str, now: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO people (id, display_name, status, first_seen_at, last_seen_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    status = excluded.status,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                (person_id, display_name, status, now, now, now, now),
            )

    def touch_person(self, person_id: str, now: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE people SET last_seen_at = ?, updated_at = ? WHERE id = ?",
                (now, now, person_id),
            )

    def rename_person(self, person_id: str, display_name: str, now: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE people
                SET display_name = ?, status = 'known', updated_at = ?
                WHERE id = ?
                """,
                (display_name, now, person_id),
            )
            self._conn.execute(
                """
                UPDATE visits
                SET display_label = ?
                WHERE person_id = ?
                """,
                (display_name, person_id),
            )

    def start_visit(
        self,
        visit_id: str,
        display_label: str,
        camera_name: str,
        started_at: str,
        enter_reason: str,
        person_id: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO visits (id, person_id, display_label, started_at, status, enter_reason, camera_name)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (visit_id, person_id, display_label, started_at, enter_reason, camera_name),
            )

    def assign_visit_person(self, visit_id: str, person_id: str, display_label: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE visits
                SET person_id = ?, display_label = ?
                WHERE id = ?
                """,
                (person_id, display_label, visit_id),
            )

    def finish_visit(self, visit_id: str, ended_at: str, leave_reason: str, best_snapshot_path: str | None) -> None:
        with self._lock, self._conn:
            started = self._conn.execute(
                "SELECT started_at FROM visits WHERE id = ?",
                (visit_id,),
            ).fetchone()
            duration_seconds = None
            if started is not None:
                duration_seconds = max(
                    0.0,
                    (
                        datetime.fromisoformat(ended_at)
                        - datetime.fromisoformat(started["started_at"])
                    ).total_seconds(),
                )
            self._conn.execute(
                """
                UPDATE visits
                SET ended_at = ?, duration_seconds = ?, status = 'closed',
                    leave_reason = ?, best_snapshot_path = COALESCE(?, best_snapshot_path)
                WHERE id = ?
                """,
                (ended_at, duration_seconds, leave_reason, best_snapshot_path, visit_id),
            )

    def store_face_sample(
        self,
        person_id: str | None,
        visit_id: str | None,
        track_id: str,
        captured_at: str,
        quality: float,
        image_path: str | None,
        embedding: list[float] | None,
        width: int | None,
        height: int | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO face_samples (
                    person_id, visit_id, track_id, captured_at, quality, image_path,
                    embedding_json, width, height
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    visit_id,
                    track_id,
                    captured_at,
                    quality,
                    image_path,
                    json.dumps(embedding) if embedding is not None else None,
                    width,
                    height,
                ),
            )

    def record_event(
        self,
        event_type: str,
        created_at: str,
        payload: dict,
        person_id: str | None = None,
        visit_id: str | None = None,
        track_id: str | None = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO camera_events (created_at, event_type, person_id, visit_id, track_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (created_at, event_type, person_id, visit_id, track_id, json.dumps(payload)),
            )

    def update_latest_frame(
        self,
        camera_name: str,
        created_at: str,
        frame_path: str,
        width: int,
        height: int,
        detection_count: int,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO latest_frame (camera_name, created_at, frame_path, width, height, detection_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(camera_name) DO UPDATE SET
                    created_at = excluded.created_at,
                    frame_path = excluded.frame_path,
                    width = excluded.width,
                    height = excluded.height,
                    detection_count = excluded.detection_count
                """,
                (camera_name, created_at, frame_path, width, height, detection_count),
            )

    def update_camera_config(self, camera_name: str, entry_zone: dict, occupancy_zone: dict, exit_zone: dict, now: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO camera_config (
                    camera_name, entry_zone_json, occupancy_zone_json, exit_zone_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(camera_name) DO UPDATE SET
                    entry_zone_json = excluded.entry_zone_json,
                    occupancy_zone_json = excluded.occupancy_zone_json,
                    exit_zone_json = excluded.exit_zone_json,
                    updated_at = excluded.updated_at
                """,
                (camera_name, json.dumps(entry_zone), json.dumps(occupancy_zone), json.dumps(exit_zone), now),
            )

    def people(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT p.*, COUNT(fs.id) AS sample_count
                FROM people p
                LEFT JOIN face_samples fs ON fs.person_id = p.id
                GROUP BY p.id
                ORDER BY p.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def visits(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM visits
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def active_visits(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM visits
                WHERE status = 'active'
                ORDER BY started_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_frame(self, camera_name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM latest_frame WHERE camera_name = ?",
                (camera_name,),
            ).fetchone()
        return dict(row) if row is not None else None

    def camera_config(self, camera_name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM camera_config WHERE camera_name = ?",
                (camera_name,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["entry_zone"] = json.loads(data.pop("entry_zone_json"))
        data["occupancy_zone"] = json.loads(data.pop("occupancy_zone_json"))
        data["exit_zone"] = json.loads(data.pop("exit_zone_json"))
        return data

    def person_embedding_map(self, max_samples_per_person: int = 12) -> dict[str, list[list[float]]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT person_id, embedding_json
                FROM face_samples
                WHERE person_id IS NOT NULL AND embedding_json IS NOT NULL
                ORDER BY captured_at DESC
                """
            ).fetchall()
        grouped: dict[str, list[list[float]]] = defaultdict(list)
        for row in rows:
            person_id = row["person_id"]
            if len(grouped[person_id]) >= max_samples_per_person:
                continue
            grouped[person_id].append(json.loads(row["embedding_json"]))
        return dict(grouped)

    def person_records(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM people").fetchall()
        return {row["id"]: dict(row) for row in rows}
