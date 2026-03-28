# LivingRoomCam

LivingRoomCam is the first project scaffold for a living-room presence and face-identity system.

The current cut gives you:

- A Pi capture agent that reads frames from `pi-camera`
- A local HTTP server with a dashboard and JSON API
- SQLite storage for people, visits, face samples, and camera events
- A pluggable vision backend, with an OpenCV Haar-cascade backend for early testing
- Config files and launch scripts for Pi and Mac development

## Layout

- `src/livingroomcam`: application code
- `config`: example configs for the Pi agent and the server
- `scripts`: bootstrap and run helpers
- `deploy`: service templates
- `tests`: unit tests
- `data` and `state`: local runtime output

## Roles

Pi:

- Runs `scripts/run-agent.sh`
- Captures MJPEG frames from `pi-camera`
- Sends JPEG frames to the server over HTTP

Mac or server host:

- Runs `scripts/run-server.sh`
- Receives frames, analyzes faces, tracks visits, and serves the dashboard

## Quick Start

Mac-specific handoff instructions are in `MAC_SETUP.md`.

Pi bootstrap:

```bash
./scripts/bootstrap-pi.sh
cp config/pi-agent.example.json config/pi-agent.local.json
./scripts/run-agent.sh
```

Server bootstrap:

```bash
./scripts/bootstrap-mac.sh
cp config/server.example.json config/server.local.json
./scripts/run-server.sh
```

Dashboard:

```text
http://<server-host>:8765/
```

## Notes

- The OpenCV backend is a baseline for iteration, not the final face-recognition stack.
- Known people are created by renaming stable unknown identities after review.
- The server keeps identity decisions conservative: if confidence is weak, the person remains unknown.
- The helper scripts prefer `./.venv/bin/python` automatically when it exists.
