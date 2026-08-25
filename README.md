# Hardware Deploy IDE

Two-slide flow: **configure hardware → generate firmware → compile on the server → flash or SSH-deploy → monitor**.

The original baseline (Monaco + load a `.hex` + Web Serial) is still here as a fallback. Compilation now happens in the backend with `arduino-cli`. Raspberry Pi targets get a Python/`gpiozero` service instead of a hex file.

---

## Quick start (Docker)

```bash
docker compose up --build
```

Open **http://localhost:8000** in Chrome, Edge, or Opera (desktop).

Happy path:

1. Leave **Arduino Uno**, LED on **D13**.
2. **Generate & compile**.
3. Plug in the board → **Flash to board** (Web Serial port picker).
4. After flash, Monitoring opens and serial **auto-reconnects** if the browser already has port permission; otherwise click **Connect Board**.

Without a USB cable: check **Simulated flash / skip USB (fake telemetry)** — Monitoring will show generated `KEY=value` lines (not a real board).

### Arduino Mega 2560

Same generate → compile path (FQBN `arduino:avr:mega`). **Flash to board** uses a separate **STK500v2** Web Serial programmer (`frontend/lib/stk500v2-mega.js`), not the Uno STK500v1 uploader.

### Raspberry Pi

1. Select **Raspberry Pi**, add GPIO pins, **Generate & compile** (no AVR compile).
2. Fill host/user (password optional) → **Deploy to Pi (SSH)**.
3. Monitoring **tails** `~/hw-deploy/hw-deploy.log` over SSH once a second. Use **Tail Pi logs** to restart the tail.
4. Or **Download artefact** (`app.py`) and run it on the Pi yourself.

SSH defaults can also come from the environment (never commit secrets):

```bash
export PI_SSH_HOST=192.168.1.42
export PI_SSH_USER=pi
# export PI_SSH_KEY=/path/to/id_ed25519
docker compose up --build
```

On the Pi: `python3` and `gpiozero` (`sudo apt install python3-gpiozero`). The backend writes `~/hw-deploy/app.py` and starts it with `nohup`. Logs: `~/hw-deploy/hw-deploy.log`.

---

## Local run (no Docker image)

Needs Python 3.11+ and, for real AVR hexes, [`arduino-cli`](https://arduino.github.io/arduino-cli/) with `arduino:avr`:

```bash
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install "Adafruit Unified Sensor" "DHT sensor library"
```

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

UI-only (placeholder hex, **not** flashable):

```bash
MOCK_COMPILE=1 uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Tests (mocked compiler):

```bash
cd backend && MOCK_COMPILE=1 pytest -q
```

If you serve only `frontend/` with `python3 -m http.server 8080`, the UI calls `http://localhost:8000` for `/api/*`. Prefer one process on port 8000 (FastAPI serves the static files).

---

## What was verified

| Target | Generate | Compile | Deploy |
|--------|----------|---------|--------|
| Arduino Uno | yes | `arduino-cli` | Web Serial STK500v1 + auto-reconnect |
| Nano (new / old bootloader) | yes | FQBN in registry | Same STK500v1 flasher |
| Pro Mini | yes | FQBN `arduino:avr:pro` | STK500v1 |
| Mega 2560 | yes | FQBN `arduino:avr:mega` | Web Serial STK500v2 (`stk500v2-mega.js`) |
| Raspberry Pi | Python | n/a | SSH deploy + log tail (`POST /api/pi/logs`) |

Update this table honestly after you plug in hardware.

---

## How to add a new target

1. **Registry** — add a board object to [`shared/boards.json`](shared/boards.json): `id`, `family` (`arduino` | `raspberry-pi` or a new family), `pins` with `capabilities`, `deployKind`, `defaultBaud`.
2. **Compile** — for AVR, set `fqbn` (cores already in [`backend/Dockerfile`](backend/Dockerfile)). For another architecture, `arduino-cli core install …` in that Dockerfile (or [`backend/toolchains/Dockerfile.arduino`](backend/toolchains/Dockerfile.arduino)) and keep the FQBN on the board.
3. **Generate** — Arduino and Pi are in [`backend/app/generator.py`](backend/app/generator.py) (`generate(config)`). New families: add a branch (same return shape). An LLM can replace this function later.
4. **Flash / deploy** — `flashProtocol` `stk500v1` uses arduino-web-uploader `flashProfile` keys (`uno`, `nano`, …). `stk500v2` uses `frontend/lib/stk500v2-mega.js`. `ssh` uses Paramiko + log tail.
5. **UI** — `GET /api/boards` drives the dropdown; no hardcoded pin lists.

Components live in [`shared/components.json`](shared/components.json). Pin-conflict and capability checks are in [`backend/app/validate.py`](backend/app/validate.py).

---

## Architecture

```
config → generate → compile → flash | ssh → monitor
```

| Seam | Module |
|------|--------|
| Board / pin / component contracts | `shared/*.json` + `backend/app/registry.py` |
| Code generation | `backend/app/generator.py` |
| Compile | `backend/app/compiler.py` (`arduino-cli` or `MOCK_COMPILE=1`) |
| Pi deploy | `backend/app/pi_deploy.py` (Paramiko) |
| Arduino flash | Web Serial STK500v1 (`arduino-web-uploader.js`) or STK500v2 (`stk500v2-mega.js`) |
| Pi deploy | `backend/app/pi_deploy.py` (Paramiko) + `POST /api/pi/logs` |
| Monitor | Slide B: USB serial, Pi log tail, or simulated telemetry |

API: `GET /api/health`, `/api/boards`, `/api/components`; `POST /api/generate`, `/api/compile`, `/api/pipeline`, `/api/deploy/pi`, `/api/pi/logs`.

---

## Assumptions and limits

- Flash requires a **secure context** (localhost or HTTPS) and Chromium desktop.
- Hex for STK500v1 must be **without** the bootloader (`arduino-cli --output-dir` default).
- D0/D1 are omitted from the Uno pin list (hardware serial).
- DHT22 sketches need the libraries baked into the Docker image.
- Pi has **no analog GPIO** in this registry; analog sensors need an ADC board (not generated).
- SSH uses Paramiko `AutoAddPolicy` (lab convenience). Prefer keys via `PI_SSH_KEY`. Host keys are not pinned.
- Compile sandbox is a per-request temp dir + timeout, not a gVisor jail. Do not expose this to the public internet.
- Flashing can overwrite firmware; there is no recovery UI.
- WSL2 USB serial: attach the Arduino to Windows and use Chrome **on Windows** against `http://localhost:8000`, or use usbipd. The Linux VM often does not see the COM port.

No API keys are required.

---

## License

MIT for this project. Vendored uploader: MIT, © David Buezas (`frontend/lib/NOTICE.txt`).
