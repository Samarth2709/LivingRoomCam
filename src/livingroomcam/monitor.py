from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import secrets
import uuid

from .config import ServerConfig
from .database import Database
from .types import ActiveTrack, FaceDetection
from .vision import VisionBackend


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(dt: datetime) -> str:
    return dt.isoformat()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class RoomMonitor:
    def __init__(self, config: ServerConfig, database: Database, backend: VisionBackend):
        self.config = config
        self.database = database
        self.backend = backend
        self.active_tracks: dict[str, ActiveTrack] = {}
        self.config.frame_store_dir.mkdir(parents=True, exist_ok=True)
        self.config.face_store_dir.mkdir(parents=True, exist_ok=True)
        self.database.update_camera_config(
            camera_name=self.config.camera_name,
            entry_zone=self.config.entry_zone.to_dict(),
            occupancy_zone=self.config.occupancy_zone.to_dict(),
            exit_zone=self.config.exit_zone.to_dict(),
            now=isoformat(utc_now()),
        )

    def process_frame(self, jpeg_bytes: bytes, camera_name: str | None = None) -> dict:
        now = utc_now()
        analysis = self.backend.analyze_frame(jpeg_bytes)
        camera_name = camera_name or self.config.camera_name
        frame_path = self._save_latest_frame(jpeg_bytes)
        self.database.update_latest_frame(
            camera_name=camera_name,
            created_at=isoformat(now),
            frame_path=str(frame_path),
            width=analysis.width,
            height=analysis.height,
            detection_count=len(analysis.detections),
        )
        assignments = self._associate_tracks(analysis.detections, analysis.width, analysis.height, now)
        for track_id, detection in assignments:
            track = self.active_tracks[track_id]
            self._update_track(track, detection, analysis.width, analysis.height, now)
        self._expire_stale_tracks(now)
        return {
            "backend": analysis.backend_name,
            "frame_width": analysis.width,
            "frame_height": analysis.height,
            "detections": len(analysis.detections),
            "active_tracks": len(self.active_tracks),
        }

    def current_occupants(self) -> list[dict]:
        results = []
        for track in self.active_tracks.values():
            results.append(
                {
                    "track_id": track.track_id,
                    "display_name": track.display_name or "pending",
                    "status": track.person_status or "pending",
                    "zone_name": track.zone_name,
                    "sample_count": track.sample_count,
                    "good_sample_count": track.good_sample_count,
                    "last_seen_at": isoformat(track.last_seen_at),
                    "visit_id": track.visit_id,
                }
            )
        results.sort(key=lambda item: item["last_seen_at"], reverse=True)
        return results

    def rename_person(self, person_id: str, display_name: str) -> None:
        now = isoformat(utc_now())
        self.database.rename_person(person_id, display_name, now)
        for track in self.active_tracks.values():
            if track.person_id == person_id:
                track.display_name = display_name
                track.person_status = "known"

    def _associate_tracks(
        self,
        detections: list[FaceDetection],
        width: int,
        height: int,
        now: datetime,
    ) -> list[tuple[str, FaceDetection]]:
        assigned: list[tuple[str, FaceDetection]] = []
        unmatched_tracks = set(self.active_tracks.keys())
        for detection in detections:
            track_id = self._best_track_for_detection(detection, width, height, unmatched_tracks, now)
            if track_id is None:
                track_id = f"track_{uuid.uuid4().hex[:8]}"
                centroid = self._normalized_center(detection, width, height)
                zone_name = self.config.zone_name_for_point(*centroid)
                self.active_tracks[track_id] = ActiveTrack(
                    track_id=track_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    centroid=centroid,
                    zone_name=zone_name,
                    previous_zone_name="outside",
                )
            if track_id in unmatched_tracks:
                unmatched_tracks.remove(track_id)
            assigned.append((track_id, detection))
        return assigned

    def _best_track_for_detection(
        self,
        detection: FaceDetection,
        width: int,
        height: int,
        candidate_ids: set[str],
        now: datetime,
    ) -> str | None:
        best_track_id = None
        best_score = -1.0
        center = self._normalized_center(detection, width, height)
        for track_id in candidate_ids:
            track = self.active_tracks[track_id]
            age_seconds = (now - track.last_seen_at).total_seconds()
            if age_seconds > self.config.track_lost_seconds:
                continue
            distance = math.dist(center, track.centroid)
            if distance > self.config.max_track_distance:
                continue
            score = 1.0 - distance
            if best_track_id is None or score > best_score:
                best_track_id = track_id
                best_score = score
        return best_track_id

    def _update_track(
        self,
        track: ActiveTrack,
        detection: FaceDetection,
        width: int,
        height: int,
        now: datetime,
    ) -> None:
        track.last_seen_at = now
        if track.sample_count > 0:
            track.previous_zone_name = track.zone_name
        track.centroid = self._normalized_center(detection, width, height)
        track.zone_name = self.config.zone_name_for_point(*track.centroid)
        track.sample_count += 1
        if detection.quality >= self.config.good_sample_quality:
            track.good_sample_count += 1
        self._update_identity(track, detection, now)
        self._update_visit_state(track, now)
        self.database.record_event(
            event_type="track_seen",
            created_at=isoformat(now),
            person_id=track.person_id,
            visit_id=track.visit_id,
            track_id=track.track_id,
            payload={
                "zone_name": track.zone_name,
                "quality": detection.quality,
                "sample_count": track.sample_count,
                "good_sample_count": track.good_sample_count,
            },
        )

    def _update_identity(self, track: ActiveTrack, detection: FaceDetection, now: datetime) -> None:
        records = self.database.person_records()
        embeddings = self.database.person_embedding_map()
        if detection.quality >= self.config.good_sample_quality:
            for person_id, samples in embeddings.items():
                if not samples:
                    continue
                similarities = [cosine_similarity(detection.embedding, sample) for sample in samples]
                track.candidate_scores.setdefault(person_id, []).extend(similarities[:3])

        if track.person_id is None and track.good_sample_count >= self.config.min_samples_to_classify:
            best_person_id, best_score = self._best_candidate(track)
            if best_person_id is not None:
                person = records.get(best_person_id, {})
                threshold = (
                    self.config.known_match_threshold
                    if person.get("status") == "known"
                    else self.config.unknown_match_threshold
                )
                if best_score >= threshold:
                    self._assign_person(track, best_person_id, person.get("display_name", best_person_id), person.get("status", "unknown"))

        if track.person_id is None and track.good_sample_count >= self.config.min_samples_to_classify:
            person_id = self._create_unknown_person(now)
            self._assign_person(track, person_id, person_id, "unknown")

        if track.person_id is not None and detection.quality >= self.config.good_sample_quality:
            image_path = self._save_face_crop(track.person_id, detection.crop_jpeg, now)
            crop_width = detection.bbox[2]
            crop_height = detection.bbox[3]
            self.database.touch_person(track.person_id, isoformat(now))
            self.database.store_face_sample(
                person_id=track.person_id,
                visit_id=track.visit_id,
                track_id=track.track_id,
                captured_at=isoformat(now),
                quality=detection.quality,
                image_path=str(image_path) if image_path is not None else None,
                embedding=detection.embedding,
                width=crop_width,
                height=crop_height,
            )
            if detection.quality >= track.best_quality:
                track.best_quality = detection.quality
                track.best_face_path = str(image_path) if image_path is not None else track.best_face_path

    def _best_candidate(self, track: ActiveTrack) -> tuple[str | None, float]:
        best_person_id = None
        best_score = -1.0
        for person_id, scores in track.candidate_scores.items():
            if not scores:
                continue
            top_scores = sorted(scores, reverse=True)[:3]
            aggregate = sum(top_scores) / len(top_scores)
            if aggregate > best_score:
                best_person_id = person_id
                best_score = aggregate
        return best_person_id, best_score

    def _assign_person(self, track: ActiveTrack, person_id: str, display_name: str, status: str) -> None:
        track.person_id = person_id
        track.display_name = display_name
        track.person_status = status
        if track.visit_id is not None:
            self.database.assign_visit_person(track.visit_id, person_id, display_name)

    def _update_visit_state(self, track: ActiveTrack, now: datetime) -> None:
        moved_into_room = (
            track.previous_zone_name in {"outside", "entry", "exit"}
            and track.zone_name == self.config.occupancy_zone.name
        )
        appeared_inside = track.previous_zone_name == "outside" and track.zone_name == self.config.occupancy_zone.name
        if track.visit_id is None and (moved_into_room or appeared_inside):
            visit_id = f"visit_{uuid.uuid4().hex[:10]}"
            track.visit_id = visit_id
            track.entered_room = True
            self.database.start_visit(
                visit_id=visit_id,
                display_label=track.display_name or "pending",
                camera_name=self.config.camera_name,
                started_at=isoformat(now),
                enter_reason="zone-crossing",
                person_id=track.person_id,
            )
            self.database.record_event(
                event_type="visit_started",
                created_at=isoformat(now),
                person_id=track.person_id,
                visit_id=visit_id,
                track_id=track.track_id,
                payload={"zone_name": track.zone_name},
            )
        left_room = track.visit_id is not None and track.zone_name == self.config.exit_zone.name
        if left_room:
            self._close_track_visit(track, now, leave_reason="exit-zone")

    def _expire_stale_tracks(self, now: datetime) -> None:
        stale_ids: list[str] = []
        for track_id, track in self.active_tracks.items():
            age_seconds = (now - track.last_seen_at).total_seconds()
            if age_seconds <= self.config.track_lost_seconds:
                continue
            if track.visit_id is not None:
                self._close_track_visit(track, now, leave_reason="lost-track")
            stale_ids.append(track_id)
        for track_id in stale_ids:
            self.active_tracks.pop(track_id, None)

    def _close_track_visit(self, track: ActiveTrack, now: datetime, leave_reason: str) -> None:
        if track.person_id is None:
            person_id = self._create_unknown_person(now)
            self._assign_person(track, person_id, person_id, "unknown")
        if track.visit_id is not None:
            self.database.finish_visit(
                visit_id=track.visit_id,
                ended_at=isoformat(now),
                leave_reason=leave_reason,
                best_snapshot_path=track.best_face_path,
            )
            self.database.record_event(
                event_type="visit_finished",
                created_at=isoformat(now),
                person_id=track.person_id,
                visit_id=track.visit_id,
                track_id=track.track_id,
                payload={"leave_reason": leave_reason, "best_face_path": track.best_face_path},
            )
            track.visit_id = None

    def _create_unknown_person(self, now: datetime) -> str:
        person_id = f"unknown_{secrets.token_hex(3)}"
        self.database.upsert_person(person_id, person_id, "unknown", isoformat(now))
        return person_id

    def _normalized_center(self, detection: FaceDetection, width: int, height: int) -> tuple[float, float]:
        center_x, center_y = detection.center
        return (center_x / max(1, width), center_y / max(1, height))

    def _save_latest_frame(self, jpeg_bytes: bytes) -> Path:
        path = self.config.frame_store_dir / "latest.jpg"
        path.write_bytes(jpeg_bytes)
        return path

    def _save_face_crop(self, person_id: str, crop_jpeg: bytes | None, now: datetime) -> Path | None:
        if crop_jpeg is None:
            return None
        person_dir = self.config.face_store_dir / person_id
        person_dir.mkdir(parents=True, exist_ok=True)
        path = person_dir / f"{now.strftime('%Y%m%d-%H%M%S-%f')}.jpg"
        path.write_bytes(crop_jpeg)
        return path
