# LivingRoomCam Notes

This project uses the Raspberry Pi Camera Module 3 through the `pi-camera` wrapper.

## Camera Basics

```bash
pi-camera check
pi-camera still
pi-camera video
```

Camera captures are written to `~/camwork/captures`.

Remote live view from a Mac:

```bash
ssh samarth@samarth-pi \
  'bash -lc "/home/samarth/.local/bin/pi-camera video --timeout 0 --width 1280 --height 720 --framerate 30 --codec mjpeg -o -"' \
| ffplay -fflags nobuffer -flags low_delay -framedrop -f mjpeg -i -
```

## Project Entry Points

- `./scripts/run-server.sh`: start the web dashboard, database, and frame-analysis server
- `./scripts/run-agent.sh`: start the Pi capture agent that streams frames to the server
- `./scripts/bootstrap-pi.sh`: create a local venv and install Pi-side Python dependencies
- `./scripts/bootstrap-mac.sh`: create a local venv and install Mac-side Python dependencies

The helper scripts prefer `./.venv/bin/python` automatically when it exists.

## Current State

- The camera runtime is in `~/camwork/root`
- The tuning file is `~/camwork/imx708_wide_noir.json`
- The project server stores data in `data/` and runtime state in `state/`
- The first CV backend is OpenCV Haar-based and is meant as a starting point for iteration
