# Installation

Am the Map runs without physical hardware or API keys via the built-in
simulator. Live CSI requires specialized hardware (see [hardware.md](hardware.md)).

## Option A — Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

## Option B — Manual (backend + frontend separately)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Optional: ESP32 USB-serial support
pip install pyserial
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

The simulator auto-starts on launch (`SIMULATOR_ENABLED=true` by default),
so `http://localhost:8000/api/status` should show a live streaming map.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### CLI

```bash
cd cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
am-map status
```

Set `AM_MAP_API_URL` if the backend isn't at `http://localhost:8000`.

## Option C — Live hardware

1. Install backend as above (`pip install pyserial` for ESP32 serial).
2. Flash CSI firmware (ESP32) or install Nexmon / PicoScenes / Atheros CSI Tool.
3. Start the pipeline:

```bash
# ESP32 USB
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"esp32","port":"/dev/ttyUSB0"}'

# Raspberry Pi / Nexmon UDP
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","udp_port":5500}'
```

Details: [hardware.md](hardware.md), [esp32.md](esp32.md), [csi.md](csi.md).

## Optional security

```bash
# .env
API_TOKEN=your-secret-here
AI_RATE_LIMIT_PER_MINUTE=30
```

When `API_TOKEN` is set, clients must send `Authorization: Bearer …` or
`X-API-Token: …`. Leave empty for open local research use.
See [privacy.md](privacy.md).

## Optional extras

```bash
pip install torch onnxruntime reportlab open3d pyserial
```

| Package | Needed for |
|---------|------------|
| `pyserial` | ESP32 USB-serial live acquisition |
| `torch` / `onnxruntime` | Loading a real trained spatial model |
| `reportlab` | PDF report export |
| `open3d` | Point-cloud / ground-truth tooling |

## Verifying the install

```bash
am-map doctor          # or GET /api/system/doctor
am-map status
am-map map --visualize
```

Doctor reports acquisition mode, sensors online, calibration state,
auth enabled, and dependency presence.
