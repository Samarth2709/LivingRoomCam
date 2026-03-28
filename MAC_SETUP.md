# Mac Setup

This project is meant to run recognition on your Mac and keep camera capture on the Raspberry Pi.

The Pi does not have the `git` binary installed, so the easiest way to copy the repository to your Mac is to sync the folder over SSH while keeping the `.git` directory.

## 1. Copy the Repository to the Mac

Current Pi LAN IP:

```text
10.207.37.24
```

On the Mac:

```bash
mkdir -p ~/Projects
rsync -a \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude 'state' \
  --exclude '__pycache__' \
  samarth@10.207.37.24:/home/samarth/Documents/LivingRoomCam/ \
  ~/Projects/LivingRoomCam/
cd ~/Projects/LivingRoomCam
```

This copies the Git repo itself, the source code, configs, scripts, and docs, but skips Linux-only runtime files.

## 2. Bootstrap the Mac Environment

On the Mac:

```bash
./scripts/bootstrap-mac.sh
```

That creates `./.venv` and installs the current Python dependencies.

## 3. Start the Recognition Server

The default config already binds to all interfaces on port `8765`.

Run:

```bash
./scripts/run-server.sh
```

In another terminal, verify:

```bash
curl http://127.0.0.1:8765/health
```

Open the dashboard:

```text
http://127.0.0.1:8765/
```

If macOS asks whether to allow incoming connections for Python or Terminal, allow it.

## 4. Find the Mac LAN IP

On the Mac, get the Wi-Fi IP:

```bash
ipconfig getifaddr en0
```

If `en0` is empty, try:

```bash
ipconfig getifaddr en1
```

Assume the result is `192.168.1.50`. That is the address the Pi should use.

## 5. Point the Pi Agent at the Mac

On the Raspberry Pi, edit:

```text
/home/samarth/Documents/LivingRoomCam/config/pi-agent.local.json
```

Set:

```json
"server_url": "http://192.168.1.50:8765"
```

Then start the Pi agent:

```bash
cd /home/samarth/Documents/LivingRoomCam
./scripts/run-agent.sh
```

## 6. Confirm End-to-End Connectivity

From the Pi:

```bash
curl http://192.168.1.50:8765/health
```

From the Mac dashboard, you should see the latest frame update once the Pi agent is running.

The Pi camera command itself is still:

```bash
pi-camera check
pi-camera video
```

## 7. Current Scope

- The transport path is ready for Pi-to-Mac frame delivery.
- The server has a working dashboard, SQLite database, visit tracking, and rename flow for unknown people.
- The current vision backend is a baseline OpenCV Haar pipeline.
- The next step on the Mac is to replace that baseline backend with a stronger person/face detection and embedding stack.
