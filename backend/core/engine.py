"""
engine.py - Shared monitoring engine used by all three backend apps
(FastAPI, Sanic, BlackSheep).

This is the "improved" version of the standalone python/monitor.py tool.
Fixes applied here, addressing gaps from the console-only version:

  1. Deduplication + hysteresis: a channel that stays out-of-range no
     longer re-alerts every ~0.3s. It alerts once on entry, again only
     on escalation (WARNING -> CRITICAL) or after a cooldown, and emits
     a RESOLVED info alert on return to normal.
  2. Persistence: every emitted alert is written to a SQLite database
     (alerts.db) so history survives a restart and can be queried.
  3. A framework-agnostic API (start/stop/get_alerts/get_new_alerts/
     get_summary) so FastAPI, Sanic and BlackSheep can each wrap it with
     their own routing without duplicating monitoring logic.

Each backend process owns one MonitorEngine instance.
"""

import ctypes
import itertools
import os
import random
import re
import sqlite3
import queue
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque
from typing import Optional

from core.redact import redact

# --------------------------------------------------------------------------
# Paths / shared library loading (same C/C++ modules as the console tool)
# --------------------------------------------------------------------------

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CORE_DIR))
LIB_DIR = os.path.join(PROJECT_ROOT, "lib")
DEFAULT_DB_PATH = os.path.join(CORE_DIR, "alerts.db")

CHANNEL_NAMES = ["Temperature", "Pressure", "Vibration", "Voltage"]
SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

# Upper bounds for caller-supplied query sizes (protects memory, DB and LLM prompts)
MAX_LIMIT = 1000
MAX_WINDOW_MINUTES = 24 * 60.0
MAX_WINDOW_HOURS = 24.0 * 14


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


class SensorReading(ctypes.Structure):
    _fields_ = [
        ("temperature", ctypes.c_float),
        ("pressure", ctypes.c_float),
        ("vibration", ctypes.c_float),
        ("voltage", ctypes.c_float),
    ]


def load_libraries():
    daq_path = os.path.join(LIB_DIR, "libdaq.so")
    anomaly_path = os.path.join(LIB_DIR, "libanomaly.so")
    if not (os.path.exists(daq_path) and os.path.exists(anomaly_path)):
        raise FileNotFoundError(
            f"Shared libraries not found in {LIB_DIR}. Run ./build.sh from "
            "the project root first."
        )

    daq = ctypes.CDLL(daq_path)
    daq.init_daq.argtypes = [ctypes.c_uint]
    daq.read_sensors.argtypes = [ctypes.POINTER(SensorReading), ctypes.c_int]
    daq.read_sensors.restype = None

    anomaly = ctypes.CDLL(anomaly_path)
    anomaly.init_engine.argtypes = [ctypes.c_int]
    anomaly.check_anomaly.argtypes = [
        ctypes.c_int, ctypes.c_float, ctypes.c_double, ctypes.c_double,
        ctypes.POINTER(ctypes.c_int),
    ]
    anomaly.check_anomaly.restype = ctypes.c_int

    return daq, anomaly


# --------------------------------------------------------------------------
# Alert model
# --------------------------------------------------------------------------

@dataclass
class Alert:
    id: int
    timestamp: str
    source: str       # FAB, ATE, FIRMWARE, HEALTH
    severity: str      # INFO, WARNING, CRITICAL
    message: str

    def as_dict(self):
        return asdict(self)


# --------------------------------------------------------------------------
# Deduplication / hysteresis
# --------------------------------------------------------------------------

class Deduper:
    """
    Tracks the last-emitted severity per state key (e.g. "FAB:Temperature").
    An alert is emitted only when:
      - this key has never fired before, or
      - severity has escalated (WARNING -> CRITICAL), or
      - the cooldown period has elapsed since the last emission for this key.
    This turns "alert every sample while out of range" into "alert on
    state change", which is what stops a stuck sensor from flooding the feed.
    """

    def __init__(self, cooldown_seconds: float = 5.0):
        self.cooldown = cooldown_seconds
        self._state = {}  # key -> (severity, last_ts)
        self._lock = threading.Lock()

    def should_emit(self, key: str, severity: str) -> bool:
        now = time.time()
        with self._lock:
            prev = self._state.get(key)
            if prev is None:
                self._state[key] = (severity, now)
                return True
            prev_sev, prev_ts = prev
            escalated = SEVERITY_RANK[severity] > SEVERITY_RANK[prev_sev]
            cooled_down = (now - prev_ts) >= self.cooldown
            if escalated or cooled_down:
                self._state[key] = (severity, now)
                return True
            return False

    def clear(self, key: str) -> bool:
        """Returns True if the key had active (non-resolved) state to clear."""
        with self._lock:
            existed = key in self._state
            self._state.pop(key, None)
            return existed


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

class MonitorEngine:
    def __init__(self, fault_rate: float = 0.08, cooldown_seconds: float = 5.0,
                 db_path: str = DEFAULT_DB_PATH, buffer_size: int = 500,
                 scenario_interval: Optional[float] = None):
        self.fault_rate = fault_rate
        # Seconds between scripted multi-subsystem fault scenarios; 0 disables (default).
        # Env: SCENARIO_INTERVAL_SECONDS
        self.scenario_interval = (float(os.environ.get("SCENARIO_INTERVAL_SECONDS", "0"))
                                  if scenario_interval is None else scenario_interval)
        self.scenarios = []  # ground truth for evaluation: [{name, start, end, first_alert_id, last_alert_id}]
        self.db_path = db_path
        self.dedup = Deduper(cooldown_seconds)
        self.buffer = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()
        self.counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
        self._stop_event = threading.Event()
        self._threads = []
        self._started = False
        self.daq = None
        self.anomaly = None
        self._write_q = queue.Queue()
        self._writer = None
        self._init_db()  # also initializes self._id_counter, resumed from any existing DB rows

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        self.daq, self.anomaly = load_libraries()
        self.daq.init_daq(int(time.time()))
        self.anomaly.init_engine(50)

        self._writer = threading.Thread(target=self._writer_loop, name="alert-writer", daemon=True)
        self._writer.start()

        loops = [self._fab_loop, self._ate_loop, self._firmware_loop, self._health_loop]
        if self.scenario_interval > 0:
            from core.simulator import run_scenarios
            loops.append(lambda: run_scenarios(self, self._stop_event, self.scenario_interval))
        self._threads = [threading.Thread(target=fn, daemon=True) for fn in loops]
        for t in self._threads:
            t.start()

    def stop(self, timeout: float = 5.0):
        """Stop monitor threads, then flush every queued alert to SQLite before returning."""
        self._stop_event.set()
        deadline = time.time() + timeout
        for t in self._threads:
            t.join(max(0.0, deadline - time.time()))
        self._write_q.put(None)  # sentinel: writer drains the queue, then exits
        if self._writer is not None:
            self._writer.join(max(0.5, deadline - time.time()))
        self._writer = None
        self._started = False

    # -- persistence ---------------------------------------------------------

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL
            )"""
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_src_ts ON alerts(source, timestamp)")
        conn.commit()
        # Resume the id sequence after whatever is already in this DB file,
        # so restarting against an existing alerts.db never collides with
        # previously persisted rows (this caused a UNIQUE constraint error
        # before the fix: the in-memory counter used to reset to 1 on every
        # process start regardless of what was already on disk).
        row = conn.execute("SELECT MAX(id) FROM alerts").fetchone()
        max_id = row[0] if row and row[0] is not None else 0
        conn.close()
        self._id_counter = itertools.count(max_id + 1)

    def _persist(self, alert: Alert):
        """Queue the alert; a single writer thread does the SQLite I/O so sensor loops never block on disk."""
        if self._writer is None:      # engine not started (e.g. unit tests): write synchronously
            self._write_batch([alert])
        else:
            self._write_q.put(alert)

    def _write_batch(self, alerts):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                "INSERT INTO alerts (id, timestamp, source, severity, message) VALUES (?,?,?,?,?)",
                [(a.id, a.timestamp, a.source, a.severity, a.message) for a in alerts],
            )
            conn.commit()
        finally:
            conn.close()

    def _writer_loop(self):
        done = False
        while not done:
            batch = []
            item = self._write_q.get()          # block until there is work
            while True:
                if item is None:
                    done = True
                else:
                    batch.append(item)
                if done or len(batch) >= 200:
                    break
                try:
                    item = self._write_q.get_nowait()
                except queue.Empty:
                    break
            if batch:
                try:
                    self._write_batch(batch)
                except Exception as e:  # never let a DB error kill the writer thread
                    print(f"[engine] failed to persist {len(batch)} alert(s): {e}")

    # -- emission ---------------------------------------------------------

    def _emit(self, source: str, severity: str, message: str, key: Optional[str] = None):
        if key is not None and not self.dedup.should_emit(key, severity):
            return
        message = redact(message)  # mask secrets before buffer / SQLite / API / WebSocket / LLM
        alert = Alert(
            id=next(self._id_counter),
            timestamp=datetime.now().isoformat(timespec="milliseconds"),
            source=source, severity=severity, message=message,
        )
        with self.buffer_lock:
            self.buffer.append(alert)
            self.counts[severity] += 1
        self._persist(alert)

    def _resolve(self, key: str, source: str, label: str):
        if self.dedup.clear(key):
            self._emit(source, "INFO", f"{label} back to normal (resolved)")

    # -- query API (used by all three backends) ---------------------------

    def get_alerts(self, limit: int = 50, severity: Optional[str] = None):
        limit = int(_clamp(limit, 1, MAX_LIMIT))
        with self.buffer_lock:
            items = list(self.buffer)
        if severity:
            items = [a for a in items if a.severity == severity.upper()]
        return [a.as_dict() for a in items[-limit:]]

    def get_new_alerts(self, since_id: int = 0):
        with self.buffer_lock:
            return [a.as_dict() for a in self.buffer if a.id > since_id]

    def get_summary(self):
        with self.buffer_lock:
            return dict(self.counts)

    def get_recent_window(self, minutes: float = 5.0):
        """In-memory alerts from the last N minutes -- used to feed a burst
        of recent activity to the AI root-cause hypothesis."""
        minutes = _clamp(minutes, 0.0, MAX_WINDOW_MINUTES)
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self.buffer_lock:
            items = list(self.buffer)
        return [
            a.as_dict() for a in items
            if datetime.fromisoformat(a.timestamp) >= cutoff
        ]

    def get_history_window(self, hours: float = 8.0, source: Optional[str] = None):
        """Persisted alerts from the last N hours -- used for shift reports."""
        hours = _clamp(hours, 0.0, MAX_WINDOW_HOURS)
        cutoff = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        q = "SELECT * FROM alerts WHERE timestamp >= ?"
        params = [cutoff.isoformat(timespec="milliseconds")]
        if source:
            q += " AND source = ?"
            params.append(source.upper())
        q += " ORDER BY id ASC"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_history(self, limit: int = 100, source: Optional[str] = None):
        limit = int(_clamp(limit, 1, MAX_LIMIT))
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        q = "SELECT * FROM alerts"
        params = ()
        if source:
            q += " WHERE source = ?"
            params = (source.upper(),)
        q += " ORDER BY id DESC LIMIT ?"
        params = params + (limit,)
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # -- monitor loops (ported from the console tool, now with dedup/hysteresis) --

    def _fab_loop(self):
        reading = SensorReading()
        severity_out = ctypes.c_int(0)
        while not self._stop_event.is_set():
            inject_fault = 1 if random.random() < self.fault_rate else 0
            self.daq.read_sensors(ctypes.byref(reading), inject_fault)
            values = [reading.temperature, reading.pressure, reading.vibration, reading.voltage]
            for cid, value in enumerate(values):
                name = CHANNEL_NAMES[cid]
                key = f"FAB:{name}"
                flagged = self.anomaly.check_anomaly(
                    cid, ctypes.c_float(value), 3.0, 5.0, ctypes.byref(severity_out)
                )
                if flagged:
                    sev = "CRITICAL" if severity_out.value == 2 else "WARNING"
                    self._emit("FAB", sev, f"{name} out of range: {value:.2f}", key=key)
                else:
                    self._resolve(key, "FAB", name)
            time.sleep(0.3)

    ATE_TESTS = [
        ("Functional_Scan", 0.02), ("Leakage_Current", 0.03),
        ("Vdd_Parametric", 0.015), ("IO_Timing", 0.02), ("Burn_In", 0.01),
    ]

    def _ate_loop(self):
        die_index = 0
        while not self._stop_event.is_set():
            die_index += 1
            for test_name, fail_prob in self.ATE_TESTS:
                if random.random() < fail_prob:
                    # Each die/test failure is a distinct real-world event,
                    # so no dedup key -- these should not be suppressed.
                    self._emit(
                        "ATE", "CRITICAL",
                        f"Die #{die_index}: FAIL on test '{test_name}' (bin {random.randint(2, 9)})",
                    )
            time.sleep(0.6)

    FIRMWARE_LOG_LINES = [
        "INFO boot: init complete", "INFO sensor: calibration ok", "DEBUG heartbeat",
        "WARN i2c: retry on bus 2",
        "ERROR NULL_PTR_DEREF at 0x0000A3F1 in task_sensor_poll",
        "ERROR WDT_RESET: watchdog timeout in main_loop",
        "PANIC stack overflow in isr_handler",
        "ERROR flash write failed, sector 0x12",
        "WARN queue: buffer 90% full",
    ]
    FIRMWARE_ISSUE_PATTERN = re.compile(r"\b(ERROR|PANIC|WDT_RESET|NULL_PTR)\b")

    def _firmware_loop(self):
        while not self._stop_event.is_set():
            line = random.choices(
                self.FIRMWARE_LOG_LINES, weights=[10, 10, 15, 3, 1, 1, 1, 1, 2]
            )[0]
            if self.FIRMWARE_ISSUE_PATTERN.search(line):
                severity = "CRITICAL" if ("PANIC" in line or "WDT_RESET" in line) else "WARNING"
                # dedup on the exact message so a repeating identical error
                # (e.g. the same watchdog reset firing every cycle) collapses,
                # but distinct error types still each get through.
                self._emit("FIRMWARE", severity, f"device log: {line}", key=f"FIRMWARE:{line}")
            time.sleep(0.5)

    def _health_loop(self):
        while not self._stop_event.is_set():
            cpu = random.uniform(20, 95)
            mem = random.uniform(30, 95)
            disk_free_gb = random.uniform(5, 500)

            cpu_key = "HEALTH:CPU"
            if cpu > 90:
                self._emit("HEALTH", "CRITICAL", f"Controller CPU usage critical: {cpu:.1f}%", key=cpu_key)
            elif cpu > 80:
                self._emit("HEALTH", "WARNING", f"Controller CPU usage high: {cpu:.1f}%", key=cpu_key)
            else:
                self._resolve(cpu_key, "HEALTH", "CPU usage")

            mem_key = "HEALTH:MEM"
            if mem > 90:
                self._emit("HEALTH", "CRITICAL", f"Controller memory usage critical: {mem:.1f}%", key=mem_key)
            else:
                self._resolve(mem_key, "HEALTH", "Memory usage")

            disk_key = "HEALTH:DISK"
            if disk_free_gb < 10:
                self._emit("HEALTH", "WARNING", f"Low disk space on log volume: {disk_free_gb:.1f} GB free", key=disk_key)
            else:
                self._resolve(disk_key, "HEALTH", "Disk space")

            time.sleep(1.0)
