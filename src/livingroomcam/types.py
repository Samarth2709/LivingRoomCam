from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]
    quality: float
    embedding: list[float]
    crop_jpeg: bytes | None = None

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.bbox
        return (x + (w / 2.0), y + (h / 2.0))


@dataclass
class FrameAnalysis:
    width: int
    height: int
    detections: list[FaceDetection] = field(default_factory=list)
    backend_name: str = "noop"


@dataclass
class ActiveTrack:
    track_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    centroid: tuple[float, float]
    zone_name: str = "outside"
    previous_zone_name: str = "outside"
    sample_count: int = 0
    good_sample_count: int = 0
    person_id: str | None = None
    person_status: str | None = None
    display_name: str | None = None
    visit_id: str | None = None
    entered_room: bool = False
    best_quality: float = 0.0
    best_face_path: str | None = None
    stored_samples: int = 0
    candidate_scores: dict[str, list[float]] = field(default_factory=dict)
