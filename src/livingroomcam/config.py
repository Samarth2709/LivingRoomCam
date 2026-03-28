from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(frozen=True)
class Zone:
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "Zone":
        return cls(
            name=str(data["name"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
            x2=float(data["x2"]),
            y2=float(data["y2"]),
        )

    def to_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    camera_name: str = "living-room-cam-1"
    db_path: Path = Path("data/livingroomcam.sqlite3")
    frame_store_dir: Path = Path("state/frames")
    face_store_dir: Path = Path("state/faces")
    static_dir: Path = Path("static")
    vision_backend: str = "opencv_haar"
    track_lost_seconds: float = 8.0
    min_samples_to_classify: int = 3
    known_match_threshold: float = 0.94
    unknown_match_threshold: float = 0.88
    max_track_distance: float = 0.12
    good_sample_quality: float = 0.18
    entry_zone: Zone = field(
        default_factory=lambda: Zone("entry", 0.0, 0.0, 0.28, 1.0)
    )
    occupancy_zone: Zone = field(
        default_factory=lambda: Zone("occupancy", 0.18, 0.0, 1.0, 1.0)
    )
    exit_zone: Zone = field(
        default_factory=lambda: Zone("exit", 0.0, 0.0, 0.18, 1.0)
    )

    @property
    def zones(self) -> list[Zone]:
        return [self.entry_zone, self.occupancy_zone, self.exit_zone]

    def zone_name_for_point(self, x: float, y: float) -> str:
        if self.entry_zone.contains(x, y):
            return self.entry_zone.name
        if self.exit_zone.contains(x, y):
            return self.exit_zone.name
        if self.occupancy_zone.contains(x, y):
            return self.occupancy_zone.name
        return "outside"


@dataclass(frozen=True)
class PiAgentConfig:
    server_url: str
    camera_name: str = "living-room-cam-1"
    send_fps: float = 2.0
    request_timeout_seconds: float = 10.0
    connect_retry_seconds: float = 3.0
    state_dir: Path = Path("state/agent")
    camera_command: list[str] = field(
        default_factory=lambda: [
            str(Path.home() / ".local/bin/pi-camera"),
            "video",
            "--timeout",
            "0",
            "--width",
            "1280",
            "--height",
            "720",
            "--framerate",
            "10",
            "--codec",
            "mjpeg",
            "-o",
            "-",
        ]
    )


def _resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_server_config(path: str | Path) -> ServerConfig:
    config_path = Path(path).expanduser().resolve()
    base_dir = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
    raw = json.loads(config_path.read_text())
    return ServerConfig(
        host=str(raw.get("host", "0.0.0.0")),
        port=int(raw.get("port", 8765)),
        camera_name=str(raw.get("camera_name", "living-room-cam-1")),
        db_path=_resolve_path(base_dir, raw.get("db_path", "data/livingroomcam.sqlite3")),
        frame_store_dir=_resolve_path(base_dir, raw.get("frame_store_dir", "state/frames")),
        face_store_dir=_resolve_path(base_dir, raw.get("face_store_dir", "state/faces")),
        static_dir=_resolve_path(base_dir, raw.get("static_dir", "static")),
        vision_backend=str(raw.get("vision_backend", "opencv_haar")),
        track_lost_seconds=float(raw.get("track_lost_seconds", 8.0)),
        min_samples_to_classify=int(raw.get("min_samples_to_classify", 3)),
        known_match_threshold=float(raw.get("known_match_threshold", 0.94)),
        unknown_match_threshold=float(raw.get("unknown_match_threshold", 0.88)),
        max_track_distance=float(raw.get("max_track_distance", 0.12)),
        good_sample_quality=float(raw.get("good_sample_quality", 0.18)),
        entry_zone=Zone.from_dict(raw.get("entry_zone", Zone("entry", 0.0, 0.0, 0.28, 1.0).to_dict())),
        occupancy_zone=Zone.from_dict(
            raw.get("occupancy_zone", Zone("occupancy", 0.18, 0.0, 1.0, 1.0).to_dict())
        ),
        exit_zone=Zone.from_dict(raw.get("exit_zone", Zone("exit", 0.0, 0.0, 0.18, 1.0).to_dict())),
    )


def load_pi_agent_config(path: str | Path) -> PiAgentConfig:
    config_path = Path(path).expanduser().resolve()
    base_dir = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
    raw = json.loads(config_path.read_text())
    return PiAgentConfig(
        server_url=str(raw["server_url"]).rstrip("/"),
        camera_name=str(raw.get("camera_name", "living-room-cam-1")),
        send_fps=float(raw.get("send_fps", 2.0)),
        request_timeout_seconds=float(raw.get("request_timeout_seconds", 10.0)),
        connect_retry_seconds=float(raw.get("connect_retry_seconds", 3.0)),
        state_dir=_resolve_path(base_dir, raw.get("state_dir", "state/agent")),
        camera_command=[str(item) for item in raw.get("camera_command", [])],
    )
