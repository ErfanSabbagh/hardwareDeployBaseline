# Hardware Deploy IDE — Baseline Demonstrator

This repository is the **starting point** for a take-home exercise.  
It is a minimal browser-based Arduino Uno IDE that can:

1. Edit a sketch (Monaco editor)
2. Flash a pre-compiled Intel HEX file to an Arduino Uno-class board over **Web Serial** (STK500v1)
3. Open a live serial monitor

It does **not** compile code, does **not** support Raspberry Pi, and has no multi-slide configuration flow. Those are the improvements described in [`ASSIGNMENT.md`](./ASSIGNMENT.md).

---

## Quick start

```bash
cd frontend
python3 -m http.server 8000
```

Open **http://localhost:8000** in Chrome, Edge, or Opera (desktop).

### Flashing a sketch

1. Write or paste code in the editor (or load the Blink sample).
2. In the **Arduino IDE** (or `arduino-cli`):
   - Board: Arduino Uno
   - Sketch → **Export compiled Binary**
   - Use the `.hex` file **without** `_with_bootloader` in the name.
3. In the web app: **Load .hex** → select board → **Flash to Board**.
4. After “Done!”, click **Connect Board** to use the serial monitor.

### Requirements

| Item | Notes |
|------|--------|
| Browser | Chrome / Edge / Opera (desktop only) |
| Context | `http://localhost` or HTTPS |
| Hardware | Arduino Uno, Nano, or Pro Mini (STK500v1 bootloader) |
| Hex file | Produced externally; must not include the bootloader |

---

## Project layout

```
hardware-deploy-baseline/
├── frontend/
│   ├── index.html                 # UI shell
│   ├── style.css                  # Dark theme
│   ├── app.js                     # Editor, serial monitor, hex wiring
│   └── lib/
│       └── arduino-web-uploader.js  # Vendored STK500v1 flasher
├── ASSIGNMENT.md                  # Take-home brief for candidates
└── README.md                      # This file
```

---

## Baseline limitations (intentional)

- Compilation is **client-external** (Arduino IDE / CLI only).
- Only STK500v1 Arduino-compatible boards are supported by the included flasher.
- Single-page UI; no hardware-configuration wizard.
- No backend, no authentication, no multi-user concerns.

See **ASSIGNMENT.md** for the three directions we want candidates to evolve this baseline toward.

---

## License

MIT for the demonstrator code. The vendored `arduino-web-uploader` retains its original MIT license (© David Buezas).
