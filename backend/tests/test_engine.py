import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.engine import MonitorEngine


def _engine(**kw):
    return MonitorEngine(db_path=os.path.join(tempfile.mkdtemp(), "t.db"), **kw)


def test_queued_writes_are_flushed_on_stop():
    e = _engine(scenario_interval=0)
    e.start()
    for i in range(300):
        e._emit("ATE", "CRITICAL", f"Die #{i}: FAIL on test 'x' password=hunter{i}")
    e.stop()  # must drain the writer queue
    rows = e.get_history(limit=1000, source="ATE")
    assert len(rows) >= 300
    assert all("hunter" not in r["message"] for r in rows)


def test_query_caps():
    e = _engine(scenario_interval=0)
    e._emit("HEALTH", "INFO", "x")
    assert len(e.get_history(limit=10**9)) <= 1000
    assert isinstance(e.get_recent_window(minutes=10**9), list)
    assert isinstance(e.get_history_window(hours=10**9), list)


def test_correlated_scenario_produces_cross_subsystem_alerts():
    from core import simulator
    e = _engine(scenario_interval=0)
    stop = __import__("threading").Event()
    # run one scenario with zero delays to keep the test fast
    gen = simulator._cooling_failure(e)
    for _, action in gen:
        action()
    sources = {a["source"] for a in e.get_alerts(limit=100)}
    assert {"FAB", "ATE", "FIRMWARE", "HEALTH"} <= sources
