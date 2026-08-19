# Hardware Deploy IDE — Take-Home Exercise

**Project:** Web-based agentic hardware deployment  
**Time we expect:** about 8–14 hours  
**Please send it back within:** 5 days of receiving it  
**Baseline stack:** static frontend (HTML / JS / CSS) + Web Serial API  
**Target stack (your work):** frontend + backend compilation + multi-target support + agentic config → deploy flow

---

## Why this exercise

We are building an **agentic platform for end-to-end hardware deployment**.  
A non-expert user should be able to:

1. Describe the hardware (board type, which pins connect to which sensors / actuators),
2. Let an agent (or deterministic generator) produce firmware,
3. Have that firmware compiled and flashed to the real device,
4. Land on a live monitoring dashboard.

Today we ship a **minimal demonstrator** that only supports Arduino Uno-class boards, requires the user to supply a pre-compiled `.hex`, and has a single-page editor + serial monitor.

Your job is to turn this baseline into a credible foundation for the product direction above.

---

## What you’ll receive

```
hardware-deploy-baseline/
├── frontend/                     # working demonstrator (treat as starting point)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── lib/
│       └── arduino-web-uploader.js   # STK500v1 Web Serial flasher (vendored)
├── ASSIGNMENT.md                 # this file
└── README.md                     # how to run the baseline
```

**Quick orientation**

```bash
cd frontend
python3 -m http.server 8000
# open http://localhost:8000
```

Requirements for the baseline flasher:

- Chrome / Edge / Opera (desktop)
- HTTPS or `http://localhost`
- A real Arduino Uno (or compatible) + a `.hex` produced by the Arduino IDE (“Export compiled Binary”, **without** bootloader)

The baseline deliberately does **not** compile code in the browser and does **not** support Raspberry Pi or other targets.

---

## What we’d like you to build

Evolve the baseline in three directions. You do not need to ship a production-ready multi-cloud product; we care about architecture, clear seams, and a working path that demonstrates the vision.

### 1. Multi-target hardware support

Generalise beyond a single Arduino Uno.

- Support at least:
  - Arduino family (Uno, Nano, and ideally one more such as Mega or a common clone)
  - Raspberry Pi (any practical path: generate Python / a simple service, deploy over SSH, or document a realistic agent-driven deploy story)
- The UI and backend contracts should make adding a new target a deliberate, documented extension point (board registry, flash strategy, compile strategy, pin model, …).
- You may keep Web Serial for Arduino-class boards; for Raspberry Pi choose whatever is pragmatic and explain the trade-offs.

### 2. Backend compilation

Move compilation off the client.

- The browser should send source (or a structured intent) to a backend.
- The backend produces the artefact that will be flashed / deployed (`.hex`, binary, Python package, container image, …).
- Prefer a real toolchain where feasible (`arduino-cli`, cross-compilers, etc.). Dockerised sandboxes are encouraged.
- Surface compile errors cleanly in the UI.
- Document how a new board’s toolchain is registered.

A minimal but working “compile this sketch for Uno → return hex” endpoint is more valuable than a large unfinished design.

### 3. Agentic end-to-end deploy flow (two-slide UX)

This is the product direction we care about most.

**Slide A — Hardware configuration (landing)**  
The user declares:

- target hardware type,
- input pins and what is connected to each (sensor type / role),
- output pins and what is connected to each (actuator type / role),
- any high-level behaviour intent (optional free text is fine).

**Slide B — Monitoring dashboard**  
After the pipeline runs, the user lands on a live view (serial / logs / simple telemetry). The baseline serial monitor can be the starting point.

**Pipeline the agent (or deterministic generator) should own**

```
config (pins + sensors/actuators + intent)
        ↓
   code generation
        ↓
   backend compilation
        ↓
   flash / deploy to the physical device
        ↓
   monitoring dashboard
```

You may start with a **deterministic code generator** (templates + pin map) and leave a clear seam for an LLM agent later. A fully agentic LLM loop is a bonus, not a requirement.

The UI should feel like two distinct modes/slides, not a single overloaded editor page.

---

## Suggested shape after your work (illustrative)

You are free to reorganise; this is one coherent target layout:

```
hardware-deploy-baseline/
├── frontend/                 # evolved UI (config slide + dashboard slide)
├── backend/                  # compilation + (optional) code-gen service
│   ├── app/                  # FastAPI / Express / … 
│   ├── toolchains/           # or Dockerfiles per target
│   └── ...
├── shared/                   # board registry, pin schemas, contracts (optional)
├── docker-compose.yml        # optional but valued
├── README.md                 # how to run everything end-to-end
└── ASSIGNMENT.md
```

---

## What we’re looking for

| Area | We care about |
|------|----------------|
| Architecture | Clear boundaries between config → generate → compile → flash → monitor; easy to swap generators or toolchains |
| Multi-target | Honest support (or a credible path) for both Arduino-class and Raspberry Pi; documented extension points |
| Backend compilation | Real artefacts produced server-side; errors visible; not just a stub that echoes the source |
| UX flow | Distinct configuration slide and monitoring slide; the “happy path” can be completed without opening an external IDE |
| Judgment | Reasonable scope cuts, explicit assumptions, security notes around flashing and remote deploy |
| Code quality | Readable structure, minimal magic, a README that lets us run your solution in a few commands |

You do **not** need perfect industrial-grade sandboxing or a full LLM agent framework. Show the seams and a working vertical slice.

---

## Optional extras (only if you have time left)

- LLM-backed code generation behind the same interface as the deterministic generator.
- Basic auth or signed upload tokens for the compile endpoint.
- A second Arduino-compatible board fully wired (compile + flash).
- Simple automated smoke test that mocks the serial port / compile step.
- Pin-conflict validation and a small component library (DHT22, relay, LED, …).

None of these are required for a solid submission.

---

## How to send it back

Push the work to a GitHub repository (public or private with access for us). Keep enough of the baseline that we can still see the starting point, or call out clearly what you replaced.

In the README include:

- how to install and run the full flow (frontend + backend),
- which boards / targets you actually verified,
- how to add a new target (even if only documented),
- assumptions and known limitations,
- any secrets / API keys required (prefer none).

We will review by:

```bash
# following your README
# then exercising: configure pins → generate → compile → flash (or simulated flash) → monitor
```

---

## Context for the broader role

The person who owns this foundation will later:

- plug real LLM agents into the code-generation step,
- expand the target catalogue (ESP32, STM32, industrial SBCs, …),
- harden the remote-deploy and safety story,
- connect the monitoring side to broader observability and digital-twin tooling.

This exercise is the vertical slice we want to see first.

---

Thanks for taking the time. Looking forward to seeing how you’d turn the demonstrator into an agentic hardware-deploy path.