# Mac GitHub Setup

Use this flow on your Mac now that the project is published on GitHub.

## 1. Clone the Project

```bash
mkdir -p ~/Projects
git clone https://github.com/Samarth2709/LivingRoomCam.git ~/Projects/LivingRoomCam
cd ~/Projects/LivingRoomCam
```

## 2. Bootstrap the Python Environment

```bash
./scripts/bootstrap-mac.sh
```

This creates `./.venv` and installs the current Python dependencies.

## 3. Start the Recognition Server

```bash
./scripts/run-server.sh
```

Verify:

```bash
curl http://127.0.0.1:8765/health
```

Open the dashboard:

```text
http://127.0.0.1:8765/
```

If macOS prompts for incoming network access, allow it.

## 4. Find the Mac LAN IP

```bash
ipconfig getifaddr en0
```

If needed:

```bash
ipconfig getifaddr en1
```

Assume the result is `192.168.1.50`.

## 5. Point the Pi at the Mac

On the Raspberry Pi, edit:

```text
/home/samarth/Documents/LivingRoomCam/config/pi-agent.local.json
```

Set:

```json
"server_url": "http://192.168.1.50:8765"
```

Then run:

```bash
cd /home/samarth/Documents/LivingRoomCam
./scripts/run-agent.sh
```

## 6. Confirm the Connection

From the Pi:

```bash
curl http://192.168.1.50:8765/health
```

From the Mac dashboard, the latest frame should start updating.

## 7. Current Backend

- The Pi-to-Mac frame transport is working.
- The Mac server has the dashboard, SQLite storage, visit tracking, and rename flow.
- The current CV backend is OpenCV Haar-based and is only a starting point.
- The next major step is replacing that backend with a stronger face detection and embedding stack on the Mac.
