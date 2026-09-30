#!/usr/bin/env python3
"""
monitor.py - Real-Time Issue Monitor for a Semiconductor Company

Pulls together four issue sources that matter on a real fab / test floor
and reports them as they happen:

  1. Fab process anomalies   -- C module (daq.c) generates raw sensor data,
                                 C++ module (anomaly_engine.cpp) flags
                                 statistical outliers in real time.
  2. ATE test failures       -- simulated wafer/die test results (functional,
                                 leakage, parametric bins).
  3. Firmware/embedded bugs  -- a simulated device log stream is scanned for
                                 crash/error/watchdog signatures.
  4. Equipment/system health -- CPU, memory and disk usage of the tool
                                 controller itself.

Each source runs on its own thread and pushes Alert objects onto a shared
queue; a single consumer thread prints and logs them in real time so
issues from every layer show up on one unified console as they occur.

Usage:
    python3 monitor.py                 # run until Ctrl+C
    python3 monitor.py --duration 30   # run for 30 seconds then stop
    python3 monitor.py --fault-rate 0.1  # 10% chance of injected sensor fault
"""

import argparse
import ctypes
import os
import queue
import random
import re
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

# --------------------------------------------------------------------------
# Paths / shared library loading
# --------------------------------------------------------------------------

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(os.path.dirname(THIS_DIR), "lib")
LOG_PATH = os.path.join(THIS_DIR, "alerts.log")

CHANNEL_NAMES = ["Temperature", "Pressure", "Vibration", "Voltage"]


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
            "Shared libraries not found. Run ./build.sh first to compile "
            "the C and C++ modules."
        )

    daq = ctypes.CDLL(daq_path)
    daq.init_daq.argtypes = [ctypes.c_uint]
    daq.read_sensors.argtypes = [ctypes.POINTER(SensorReading), ctypes.c_int]
    daq.read_sensors.restype = None

    anomaly = ctypes.CDLL(anomaly_path)
    anomaly.init_engine.argtypes = [ctypes.c_int]
    anomaly.check_anomaly.argtypes = [
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_int),
    ]
    anomaly.check_anomaly.restype = ctypes.c_int

    return daq, anomaly


# --------------------------------------------------------------------------
# Alert model + shared console/log sink
# --------------------------------------------------------------------------

SEVERITY_COLOR = {
    "INFO": "\033[36m",      # cyan
    "WARNING": "\033[33m",   # yellow
    "CRITICAL": "\033[31m",  # red
}
RESET = "\033[0m"


@dataclass(order=True)
class Alert:
    sort_index: float = field(init=False, repr=False)
    timestamp: datetime
    source: str        # "FAB", "ATE", "FIRMWARE", "HEALTH"
    severity: str      # "INFO", "WARNING", "CRITICAL"
    message: str

    def __post_init__(self):
        self.sort_index = self.timestamp.timestamp()

    def format(self) -> str:
        color = SEVERITY_COLOR.get(self.severity, "")
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"{color}[{ts}] [{self.severity:<8}] [{self.source:<8}] {self.message}{RESET}"


class AlertBus:
    """Thread-safe sink: every issue source pushes here, one consumer drains it."""

    def __init__(self, log_path: str):
        self._q: "queue.Queue[Alert]" = queue.Queue()
        self._log_path = log_path
        self.counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
        self._lock = threading.Lock()

    def push(self, alert: Alert):
        self._q.put(alert)

    def drain_forever(self, stop_event: threading.Event):
        with open(self._log_path, "a") as logf:
            while not stop_event.is_set() or not self._q.empty():
                try:
                    alert = self._q.get(timeout=0.2)
                except queue.Empty:
                    continue
                with self._lock:
                    self.counts[alert.severity] += 1
                print(alert.format())
                logf.write(
                    f"{alert.timestamp.isoformat()},{alert.source},"
                    f"{alert.severity},{alert.message}\n"
                )
                logf.flush()


# --------------------------------------------------------------------------
# 1. Fab process anomaly monitor (C + C++)
# --------------------------------------------------------------------------

def fab_monitor(bus: AlertBus, stop_event: threading.Event, fault_rate: float,
                 daq, anomaly, interval: float = 0.3):
    daq.init_daq(int(time.time()))
    anomaly.init_engine(50)  # rolling window size

    reading = SensorReading()
    severity_out = ctypes.c_int(0)

    while not stop_event.is_set():
        inject_fault = 1 if random.random() < fault_rate else 0
        daq.read_sensors(ctypes.byref(reading), inject_fault)

        values = [reading.temperature, reading.pressure, reading.vibration, reading.voltage]
        for channel_id, value in enumerate(values):
            flagged = anomaly.check_anomaly(channel_id, ctypes.c_float(value),
                                             3.0, 5.0, ctypes.byref(severity_out))
            if flagged:
                sev = "CRITICAL" if severity_out.value == 2 else "WARNING"
                name = CHANNEL_NAMES[channel_id]
                bus.push(Alert(
                    timestamp=datetime.now(),
                    source="FAB",
                    severity=sev,
                    message=f"{name} out of range: {value:.2f} (rolling z-score anomaly)",
                ))
        time.sleep(interval)


# --------------------------------------------------------------------------
# 2. ATE (Automated Test Equipment) failure monitor
# --------------------------------------------------------------------------

ATE_TESTS = [
    ("Functional_Scan", 0.02),
    ("Leakage_Current", 0.03),
    ("Vdd_Parametric", 0.015),
    ("IO_Timing", 0.02),
    ("Burn_In", 0.01),
]


def ate_monitor(bus: AlertBus, stop_event: threading.Event, interval: float = 0.6):
    die_index = 0
    while not stop_event.is_set():
        die_index += 1
        for test_name, fail_prob in ATE_TESTS:
            if random.random() < fail_prob:
                bus.push(Alert(
                    timestamp=datetime.now(),
                    source="ATE",
                    severity="CRITICAL",
                    message=f"Die #{die_index}: FAIL on test '{test_name}' "
                             f"(bin {random.randint(2, 9)})",
                ))
        time.sleep(interval)


# --------------------------------------------------------------------------
# 3. Firmware / embedded log monitor
# --------------------------------------------------------------------------

FIRMWARE_LOG_LINES = [
    "INFO boot: init complete",
    "INFO sensor: calibration ok",
    "DEBUG heartbeat",
    "WARN i2c: retry on bus 2",
    "ERROR NULL_PTR_DEREF at 0x0000A3F1 in task_sensor_poll",
    "ERROR WDT_RESET: watchdog timeout in main_loop",
    "PANIC stack overflow in isr_handler",
    "ERROR flash write failed, sector 0x12",
    "WARN queue: buffer 90% full",
]

FIRMWARE_ISSUE_PATTERN = re.compile(r"\b(ERROR|PANIC|WDT_RESET|NULL_PTR)\b")


def firmware_monitor(bus: AlertBus, stop_event: threading.Event, interval: float = 0.5):
    while not stop_event.is_set():
        line = random.choices(
            FIRMWARE_LOG_LINES,
            weights=[10, 10, 15, 3, 1, 1, 1, 1, 2],
        )[0]
        if FIRMWARE_ISSUE_PATTERN.search(line):
            severity = "CRITICAL" if "PANIC" in line or "WDT_RESET" in line else "WARNING"
            bus.push(Alert(
                timestamp=datetime.now(),
                source="FIRMWARE",
                severity=severity,
                message=f"device log: {line}",
            ))
        time.sleep(interval)


# --------------------------------------------------------------------------
# 4. Equipment / system health monitor
# --------------------------------------------------------------------------

def health_monitor(bus: AlertBus, stop_event: threading.Event, interval: float = 1.0):
    while not stop_event.is_set():
        cpu = random.uniform(20, 95)
        mem = random.uniform(30, 95)
        disk_free_gb = random.uniform(5, 500)

        if cpu > 90:
            bus.push(Alert(datetime.now(), "HEALTH", "CRITICAL",
                            f"Controller CPU usage critical: {cpu:.1f}%"))
        elif cpu > 80:
            bus.push(Alert(datetime.now(), "HEALTH", "WARNING",
                            f"Controller CPU usage high: {cpu:.1f}%"))

        if mem > 90:
            bus.push(Alert(datetime.now(), "HEALTH", "CRITICAL",
                            f"Controller memory usage critical: {mem:.1f}%"))

        if disk_free_gb < 10:
            bus.push(Alert(datetime.now(), "HEALTH", "WARNING",
                            f"Low disk space on log volume: {disk_free_gb:.1f} GB free"))

        time.sleep(interval)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Real-time semiconductor issue monitor")
    parser.add_argument("--duration", type=float, default=None,
                         help="Run for N seconds then stop (default: run until Ctrl+C)")
    parser.add_argument("--fault-rate", type=float, default=0.08,
                         help="Probability [0-1] of an injected sensor fault per sample")
    args = parser.parse_args()

    daq, anomaly = load_libraries()

    bus = AlertBus(LOG_PATH)
    stop_event = threading.Event()

    threads = [
        threading.Thread(target=fab_monitor, args=(bus, stop_event, args.fault_rate, daq, anomaly), daemon=True),
        threading.Thread(target=ate_monitor, args=(bus, stop_event), daemon=True),
        threading.Thread(target=firmware_monitor, args=(bus, stop_event), daemon=True),
        threading.Thread(target=health_monitor, args=(bus, stop_event), daemon=True),
        threading.Thread(target=bus.drain_forever, args=(stop_event,), daemon=True),
    ]

    width = shutil.get_terminal_size((80, 20)).columns
    print("=" * width)
    print(" Semiconductor Real-Time Issue Monitor".center(width))
    print(" Sources: FAB (C/C++ sensors) | ATE | FIRMWARE logs | HEALTH".center(width))
    print(" Press Ctrl+C to stop".center(width))
    print("=" * width)

    for t in threads:
        t.start()

    try:
        start = time.time()
        while True:
            if args.duration is not None and (time.time() - start) >= args.duration:
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping monitor, flushing remaining alerts...")
        stop_event.set()
        time.sleep(0.5)  # let the drain thread catch up
        with bus._lock:
            counts = dict(bus.counts)
        total = sum(counts.values())
        print("-" * width)
        print(f"Session summary: {total} alerts "
              f"(CRITICAL={counts['CRITICAL']}, WARNING={counts['WARNING']}, INFO={counts['INFO']})")
        print(f"Full log written to: {LOG_PATH}")


if __name__ == "__main__":
    main()
