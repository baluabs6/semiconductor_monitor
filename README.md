# Semiconductor Real-Time Issue Monitor

A working example of a real-time issue-detection app for a semiconductor
company, mixing all three languages you asked for:

| Layer | Language | Role |
|---|---|---|
| Data acquisition | **C** (`c_src/daq.c`) | Fast raw sensor sampling (temperature, chamber pressure, vibration, supply voltage) |
| Anomaly detection | **C++** (`cpp_src/anomaly_engine.cpp`) | Rolling-window statistics (mean/stddev, z-score) to flag outliers — the same idea behind SPC control charts on a real fab line |
| Orchestration & alerting | **Python** (`python/monitor.py`) | Loads the C/C++ code via `ctypes`, runs 4 concurrent monitors, merges everything into one live, color-coded alert stream |

## Issue sources covered

1. **FAB** — sensor readings from the C/C++ pipeline, flagged when they drift
   outside their statistically normal range.
2. **ATE** — simulated die test results (functional scan, leakage current,
   parametric, timing, burn-in) with random fails, like a real automated
   test equipment log.
3. **FIRMWARE** — a simulated embedded device log stream, scanned for
   `ERROR` / `PANIC` / `WDT_RESET` / `NULL_PTR` signatures.
4. **HEALTH** — CPU/memory/disk of the tool controller itself.

Each source runs on its own thread; alerts are pushed to a shared queue and
printed + logged (`python/alerts.log`) in real time as they occur.

## Setup

Requires `gcc`/`g++` and Python 3.

```bash
./build.sh                 # compiles daq.c and anomaly_engine.cpp into .so files
python3 python/monitor.py  # run until Ctrl+C
```

Options:

```bash
python3 python/monitor.py --duration 30       # stop after 30 seconds
python3 python/monitor.py --fault-rate 0.2    # inject more sensor faults (default 0.08)
```

## Where this is a stand-in for real hardware

- `daq.c`'s `read_sensors()` currently generates random values. Swap this
  for real reads from your SPI/I2C sensors, DAQ card, or SECS/GEM
  equipment interface — the function signature Python calls stays the same.
- `ate_monitor()` and `firmware_monitor()` in `monitor.py` simulate data;
  point them at your real ATE log files / test database and device log
  stream (e.g. tail a serial port or syslog) instead of the built-in
  random generators.

## Backend APIs (FastAPI / Sanic / BlackSheep)

`backend/` adds a REST + WebSocket layer on top of the same C/C++ engine,
plus fixes for two of the gaps called out earlier: **alert flooding** and
**no persistence**.

- `backend/core/engine.py` — the shared engine (used by all three apps).
  New here vs. the console tool:
  - **Deduplication + hysteresis** (`Deduper`): a stuck-out-of-range sensor
    now alerts once on entry, again only on escalation (WARNING → CRITICAL)
    or after a cooldown, and emits a `RESOLVED` info alert when it returns
    to normal — instead of re-alerting every ~0.3s forever.
  - **SQLite persistence**: every alert is written to a local `.db` file,
    so history survives a restart and can be queried (`/alerts/history`).
- `backend/fastapi_app.py`, `backend/sanic_app.py`, `backend/blacksheep_app.py`
  — three independent backends exposing the identical API, so you can
  compare them or pick one:
  - `GET /health`
  - `GET /alerts?limit=50&severity=CRITICAL` — recent in-memory alerts
  - `GET /alerts/history?limit=100&source=FAB` — persisted history from SQLite
  - `GET /summary` — running counts by severity
  - `WS /ws/alerts` — live push of new alerts, polled from the engine every 0.5s

### Run one

```bash
cd backend
pip install -r requirements.txt

# FastAPI  (port 8001)
uvicorn fastapi_app:app --host 0.0.0.0 --port 8001

# Sanic    (port 8002)
python3 sanic_app.py

# BlackSheep (port 8003)
uvicorn blacksheep_app:app --host 0.0.0.0 --port 8003
```

Each app owns its own SQLite file (`alerts_fastapi.db`, `alerts_sanic.db`,
`alerts_blacksheep.db`) and can run at the same time on its own port,
so you can literally load-test/compare all three side by side.

### AI-powered features (Claude)

`backend/core/ai_insights.py` adds two Claude-powered endpoints, available
identically on all three backends:

- `GET /alerts/analyze?minutes=5` — takes the alerts from the last N minutes
  and asks Claude whether they look related, its best root-cause hypothesis,
  and one concrete next diagnostic step. Useful right after a burst of
  correlated alerts across subsystems (e.g. a FAB temperature warning plus a
  FIRMWARE watchdog reset within the same minute).
- `GET /alerts/report?hours=8&source=FAB` — turns a longer stretch of
  persisted history into a short shift-handoff report (status, notable
  incidents by subsystem, follow-ups), optionally filtered to one source.

Setup:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

If the key isn't set, both endpoints return a normal 200 response with a
clear `"AI analysis/summary unavailable: ..."` message instead of erroring,
so the rest of the API keeps working without it.

### Known limitation carried over from the design

Each backend runs the monitoring loops as **background threads inside its
own process** — fine for one instance, but if you ever run multiple
replicas of the same backend behind a load balancer, each replica will
have its own independent engine and alert history. For that setup, the
engine's data-generation threads should move into one standalone process
(or a real data source) that publishes to a shared store (Redis/Postgres)
which all API replicas read from.

## Extending it

- **Thresholds**: `sigma_warn`/`sigma_crit` are passed into `check_anomaly()`
  per call — tune per channel, or expose them as config.
- **More channels**: add entries to `CHANNEL_NAMES` / `SensorReading` in
  lockstep on the C, C++, and Python sides.
- **Notifications**: `AlertBus.drain_forever()` is the single choke point —
  add a Slack/email/webhook call there instead of (or alongside) printing.
- **Dashboard**: `alerts.log` is CSV-like (`timestamp,source,severity,message`)
  so it's easy to tail into a Grafana/Streamlit dashboard if you want a UI
  beyond the console.

## Spring AI service (Java)

`spring_ai_service/` is a Spring Boot + Spring AI (Claude) service that sits next to the Python
backend and calls its REST API. It adds typed AI endpoints (`/ai/analyze`, `/ai/report`) and a tool-calling
`/ai/chat` where Claude can query live alerts itself. C, C++ and Python are untouched. See
`spring_ai_service/README.md`.
