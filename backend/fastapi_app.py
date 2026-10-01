"""
fastapi_app.py - FastAPI backend for the semiconductor monitor.

Run:
    uvicorn fastapi_app:app --host 0.0.0.0 --port 8001
"""
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query

from core.engine import MonitorEngine
from core.redact import install_logging_redaction
from core.ai_insights import analyze_alert_burst, summarize_shift

install_logging_redaction()  # mask secrets in every log record (uvicorn, libraries, tracebacks)
engine = MonitorEngine(db_path=os.environ.get("ALERTS_DB_PATH", "alerts_fastapi.db"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.start()
    yield
    engine.stop()


app = FastAPI(title="Semiconductor Monitor - FastAPI backend", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "framework": "fastapi"}


@app.get("/alerts")
def alerts(limit: int = 50, severity: Optional[str] = Query(default=None)):
    return engine.get_alerts(limit=limit, severity=severity)


@app.get("/alerts/history")
def alerts_history(limit: int = 100, source: Optional[str] = Query(default=None)):
    return engine.get_history(limit=limit, source=source)


@app.get("/summary")
def summary():
    return engine.get_summary()


@app.get("/lots")
def lots(limit: int = 50):
    """Recent lot runs on this tool (newest first)."""
    return engine.get_lots(limit=limit)


@app.get("/containment")
def containment(hours: float = 8.0):
    """Deterministic excursion-containment report: which lots were exposed? (proposal only)"""
    return engine.get_containment(hours=hours)


@app.get("/alerts/analyze")
def analyze(minutes: float = 5.0):
    """AI root-cause hypothesis for the alert burst in the last `minutes`."""
    recent = engine.get_recent_window(minutes=minutes)
    return {"window_minutes": minutes, "alert_count": len(recent), "hypothesis": analyze_alert_burst(recent)}


@app.get("/alerts/report")
def report(hours: float = 8.0, source: Optional[str] = Query(default=None)):
    """AI shift-handoff summary for the alert history in the last `hours`."""
    history = engine.get_history_window(hours=hours, source=source)
    return {"window_hours": hours, "alert_count": len(history), "report": summarize_shift(history, hours)}


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await ws.accept()
    last_id = 0
    try:
        while True:
            new = engine.get_new_alerts(last_id)
            if new:
                last_id = new[-1]["id"]
                await ws.send_json(new)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
