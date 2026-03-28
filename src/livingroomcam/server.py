from __future__ import annotations

from argparse import ArgumentParser
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

from .config import load_server_config
from .database import Database
from .monitor import RoomMonitor
from .vision import NoopVisionBackend, build_backend


class AppServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, monitor: RoomMonitor, database: Database, config, dashboard_html: str):
        super().__init__(server_address, handler_class)
        self.monitor = monitor
        self.database = database
        self.config = config
        self.dashboard_html = dashboard_html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server: AppServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(self.server.dashboard_html)
            return
        if parsed.path == "/health":
            self._json({"status": "ok", "camera_name": self.server.config.camera_name})
            return
        if parsed.path == "/api/people":
            self._json({"people": self.server.database.people()})
            return
        if parsed.path == "/api/visits":
            self._json({"visits": self.server.database.visits()})
            return
        if parsed.path == "/api/occupants":
            self._json({"occupants": self.server.monitor.current_occupants()})
            return
        if parsed.path == "/api/config":
            self._json(
                {
                    "camera_name": self.server.config.camera_name,
                    "vision_backend": self.server.config.vision_backend,
                    "camera_config": self.server.database.camera_config(self.server.config.camera_name),
                }
            )
            return
        if parsed.path == "/api/latest-frame.jpg":
            latest = self.server.database.latest_frame(self.server.config.camera_name)
            if latest is None:
                self.send_error(HTTPStatus.NOT_FOUND, "No frame available")
                return
            frame_path = Path(latest["frame_path"])
            if not frame_path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Latest frame missing on disk")
                return
            self._bytes(frame_path.read_bytes(), "image/jpeg")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/frames":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            params = parse_qs(parsed.query)
            camera_name = params.get("camera_name", [self.server.config.camera_name])[0]
            result = self.server.monitor.process_frame(body, camera_name=camera_name)
            self._json({"ok": True, "result": result}, status=HTTPStatus.ACCEPTED)
            return
        if parsed.path.startswith("/api/people/") and parsed.path.endswith("/rename"):
            person_id = parsed.path.removeprefix("/api/people/").removesuffix("/rename").strip("/")
            payload = self._read_json()
            display_name = str(payload.get("display_name", "")).strip()
            if not display_name:
                self.send_error(HTTPStatus.BAD_REQUEST, "display_name is required")
                return
            self.server.monitor.rename_person(person_id, display_name)
            self._json({"ok": True, "person_id": person_id, "display_name": display_name})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if not body:
            return {}
        return json.loads(body)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the LivingRoomCam server")
    parser.add_argument("config", help="Path to server config JSON")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_server_config(args.config)
    database = Database(config.db_path)
    try:
        backend = build_backend(config.vision_backend)
    except Exception as exc:
        print(
            f"Falling back to noop vision backend because '{config.vision_backend}' failed: {exc}",
            file=sys.stderr,
        )
        backend = NoopVisionBackend()
    monitor = RoomMonitor(config=config, database=database, backend=backend)
    dashboard_html = config.static_dir.joinpath("dashboard.html").read_text()
    server = AppServer((config.host, config.port), Handler, monitor, database, config, dashboard_html)
    print(f"Listening on http://{config.host}:{config.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
