import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.engine import MonitorEngine
from core.genealogy import LotTracker


def _engine():
    return MonitorEngine(db_path=os.path.join(tempfile.mkdtemp(), "t.db"), scenario_interval=0)


def test_alerts_are_stamped_with_lot_context():
    e = _engine()
    e._emit("FAB", "WARNING", "Temperature out of range: 99.00")
    a = e.get_alerts(limit=1)[0]
    assert a["lot_id"].startswith("LOT-") and a["tool_id"] == "TOOL-01" and a["wafer_id"].startswith("WF-")
    assert e.get_history(limit=1)[0]["lot_id"] == a["lot_id"]          # persisted too


def test_old_database_is_migrated():
    import sqlite3
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE alerts (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, source TEXT NOT NULL, "
              "severity TEXT NOT NULL, message TEXT NOT NULL)")
    c.execute("INSERT INTO alerts VALUES (1,'2026-01-01T00:00:00.000','FAB','INFO','old row')")
    c.commit(); c.close()
    e = MonitorEngine(db_path=path, scenario_interval=0)
    e._emit("FAB", "INFO", "new row")
    rows = e.get_history(limit=10)
    assert {r["message"] for r in rows} == {"old row", "new row"} and rows[0]["lot_id"] != ""


def test_containment_lists_lots_exposed_during_excursion():
    e = _engine()
    first = e.lots.current_context()["lot_id"]
    e._emit("FAB", "CRITICAL", "Temperature out of range: 120.00", key="k1")       # lot A, critical
    e.lots.start_lot("LOT-B", "RCP-B")
    e._emit("FIRMWARE", "CRITICAL", "device log: ERROR WDT_RESET", key="k2")        # lot B, critical (extends window)
    e.lots.start_lot("LOT-C", "RCP-A")
    for i in range(4):
        e._emit("ATE", "CRITICAL", f"Die #{i}: FAIL on test 'Leakage_Current' (bin 4)")  # lot C, 4 ATE failures
    e.lots.start_lot("LOT-D", "RCP-A")                                              # after the excursion, no alerts
    rep = e.get_containment(hours=1)
    ids = {l["lot_id"]: l for l in rep["lots"]}
    assert first in ids and "LOT-B" in ids and "LOT-C" in ids
    assert "LOT-D" not in ids                                                       # never exposed
    assert ids["LOT-C"]["risk"] == "HIGH" and ids["LOT-C"]["ate_failures"] == 4
    assert ids[first]["risk"] == "HIGH" and ids[first]["critical_alerts"] == 1
    assert rep["excursion"]["critical_alerts"] == 2 and "human review" in rep["note"]


def test_no_excursion_means_no_exposed_lots():
    e = _engine()
    e._emit("HEALTH", "INFO", "all fine")
    rep = e.get_containment(hours=1)
    assert rep["excursion"] is None and rep["lots"] == []


def test_runs_overlapping_handles_open_runs():
    t = LotTracker(first_lot="L1")
    t.start_lot("L2", "RCP-A", now=datetime.now() + timedelta(seconds=1))
    now = datetime.now()
    names = {r.lot_id for r in t.runs_overlapping(now - timedelta(minutes=1), now + timedelta(minutes=1))}
    assert names == {"L1", "L2"}
