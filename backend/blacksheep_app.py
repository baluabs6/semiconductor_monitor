"""
blacksheep_app.py - BlackSheep backend for the semiconductor monitor.

Run:
    uvicorn blacksheep_app:app --host 0.0.0.0 --port 8003
"""
import asyncio

from blacksheep import Application, Request, WebSocket, json

from core.engine import MonitorEngine
from core.ai_insights import analyze_alert_burst, summarize_shift

engine = MonitorEngine(db_path="alerts_blacksheep.db")
app = Application()


@app.on_start
async def start_engine(application: Application):
    engine.start()


@app.on_stop
async def stop_engine(application: Application):
    engine.stop()


@app.router.get("/health")
async def health():
    return json({"status": "ok", "framework": "blacksheep"})


@app.router.get("/alerts")
async def alerts(request: Request):
    limit = int(request.query.get("limit", ["50"])[0])
    severity = request.query.get("severity", [None])[0]
    return json(engine.get_alerts(limit=limit, severity=severity))


@app.router.get("/alerts/history")
async def alerts_history(request: Request):
    limit = int(request.query.get("limit", ["100"])[0])
    source = request.query.get("source", [None])[0]
    return json(engine.get_history(limit=limit, source=source))


@app.router.get("/summary")
async def summary():
    return json(engine.get_summary())


@app.router.get("/alerts/analyze")
async def analyze(request: Request):
    minutes = float(request.query.get("minutes", ["5.0"])[0])
    recent = engine.get_recent_window(minutes=minutes)
    return json({
        "window_minutes": minutes, "alert_count": len(recent),
        "hypothesis": analyze_alert_burst(recent),
    })


@app.router.get("/alerts/report")
async def report(request: Request):
    hours = float(request.query.get("hours", ["8.0"])[0])
    source = request.query.get("source", [None])[0]
    history = engine.get_history_window(hours=hours, source=source)
    return json({
        "window_hours": hours, "alert_count": len(history),
        "report": summarize_shift(history, hours),
    })


@app.router.ws("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    last_id = 0
    while True:
        new = engine.get_new_alerts(last_id)
        if new:
            last_id = new[-1]["id"]
            await websocket.send_json(new)
        await asyncio.sleep(0.5)
