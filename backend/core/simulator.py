"""
simulator.py - scripted, *correlated* fault scenarios.

The default simulators fire independent random faults, which never exercises what this system is
for: spotting that a FAB sensor excursion, a firmware reset and a burst of ATE failures share one
root cause. Each scenario here is a timed cascade across subsystems. Ground truth (name, time
span, alert id range) is recorded in engine.scenarios so root-cause analysis can be evaluated.

Enable with SCENARIO_INTERVAL_SECONDS=60 (or MonitorEngine(scenario_interval=60)).
Scenario alerts use their own dedup keys (SIM:*) and are resolved explicitly at the end, so the
normal sensor loop's auto-resolve doesn't cancel them mid-cascade.
"""

import random
from datetime import datetime


def _cooling_failure(e):
    yield 0.0, lambda: e._emit("FAB", "CRITICAL", f"Temperature out of range: {random.uniform(105, 125):.2f}", key="SIM:FAB:Temperature")
    yield 2.0, lambda: e._emit("FAB", "WARNING", f"Pressure out of range: {random.uniform(1.7, 2.1):.2f}", key="SIM:FAB:Pressure")
    yield 4.0, lambda: e._emit("FIRMWARE", "CRITICAL", "device log: ERROR WDT_RESET: watchdog timeout in main_loop", key="SIM:FW:WDT")
    for i in range(3):
        yield 5.0 + i * 0.6, (lambda i=i: e._emit("ATE", "CRITICAL", f"Die #{9000 + i}: FAIL on test 'Leakage_Current' (bin {random.randint(2, 9)})"))
    yield 8.0, lambda: e._emit("HEALTH", "WARNING", f"Controller CPU usage high: {random.uniform(82, 89):.1f}%", key="SIM:HEALTH:CPU")
    yield 12.0, lambda: (e._resolve("SIM:FAB:Temperature", "FAB", "Temperature"),
                         e._resolve("SIM:FAB:Pressure", "FAB", "Pressure"),
                         e._resolve("SIM:FW:WDT", "FIRMWARE", "Watchdog"),
                         e._resolve("SIM:HEALTH:CPU", "HEALTH", "CPU usage"))


def _power_brownout(e):
    yield 0.0, lambda: e._emit("FAB", "CRITICAL", f"Voltage out of range: {random.uniform(2.2, 2.7):.2f}", key="SIM:FAB:Voltage")
    for i in range(4):
        yield 1.0 + i * 0.5, (lambda i=i: e._emit("ATE", "CRITICAL", f"Die #{9100 + i}: FAIL on test 'Vdd_Parametric' (bin {random.randint(2, 9)})"))
    yield 4.0, lambda: e._emit("FIRMWARE", "WARNING", "device log: ERROR flash write failed, sector 0x12", key="SIM:FW:FLASH")
    yield 9.0, lambda: (e._resolve("SIM:FAB:Voltage", "FAB", "Voltage"),
                        e._resolve("SIM:FW:FLASH", "FIRMWARE", "Flash writes"))


SCENARIOS = {"cooling_failure": _cooling_failure, "power_brownout": _power_brownout}


def run_scenarios(engine, stop_event, interval: float):
    while not stop_event.wait(interval):
        name = random.choice(list(SCENARIOS))
        record = {"name": name, "start": datetime.now().isoformat(timespec="milliseconds"),
                  "first_alert_id": None, "last_alert_id": None}
        t_prev = 0.0
        for t, action in SCENARIOS[name](engine):
            if stop_event.wait(max(0.0, t - t_prev)):
                return
            t_prev = t
            action()
            if record["first_alert_id"] is None:
                record["first_alert_id"] = engine.get_alerts(limit=1)[-1]["id"] if engine.get_alerts(limit=1) else None
        recent = engine.get_alerts(limit=1)
        record["last_alert_id"] = recent[-1]["id"] if recent else None
        record["end"] = datetime.now().isoformat(timespec="milliseconds")
        engine.scenarios.append(record)
