from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib import request
from urllib.error import URLError

from .config import load_pi_agent_config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jpeg_stream(stdout, chunk_size: int = 32768):
    buffer = bytearray()
    soi = b"\xff\xd8"
    eoi = b"\xff\xd9"
    while True:
        chunk = stdout.read(chunk_size)
        if not chunk:
            break
        buffer.extend(chunk)
        while True:
            start = buffer.find(soi)
            if start < 0:
                buffer.clear()
                break
            end = buffer.find(eoi, start + 2)
            if end < 0:
                if start > 0:
                    del buffer[:start]
                break
            frame = bytes(buffer[start : end + 2])
            del buffer[: end + 2]
            yield frame


def post_frame(server_url: str, camera_name: str, jpeg_bytes: bytes, timeout: float) -> dict:
    req = request.Request(
        f"{server_url}/api/frames?camera_name={camera_name}",
        data=jpeg_bytes,
        method="POST",
        headers={"Content-Type": "image/jpeg"},
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8"))


def write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the LivingRoomCam Pi agent")
    parser.add_argument("config", help="Path to pi-agent config JSON")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_pi_agent_config(args.config)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    state_path = config.state_dir / "agent-status.json"
    min_interval = 1.0 / max(config.send_fps, 0.1)

    while True:
        started_at = utc_now()
        process = subprocess.Popen(
            config.camera_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        try:
            last_sent = 0.0
            frames_sent = 0
            for frame in jpeg_stream(process.stdout):
                now = time.monotonic()
                if now - last_sent < min_interval:
                    continue
                response = post_frame(
                    server_url=config.server_url,
                    camera_name=config.camera_name,
                    jpeg_bytes=frame,
                    timeout=config.request_timeout_seconds,
                )
                frames_sent += 1
                last_sent = now
                write_state(
                    state_path,
                    {
                        "started_at": started_at,
                        "last_posted_at": utc_now(),
                        "frames_sent": frames_sent,
                        "server_url": config.server_url,
                        "last_response": response,
                    },
                )
        except KeyboardInterrupt:
            process.terminate()
            raise
        except URLError as exc:
            write_state(
                state_path,
                {
                    "started_at": started_at,
                    "last_error_at": utc_now(),
                    "error": f"server-unreachable: {exc}",
                },
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
        time.sleep(config.connect_retry_seconds)


if __name__ == "__main__":
    main()
