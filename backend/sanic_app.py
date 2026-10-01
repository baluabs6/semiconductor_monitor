"""
sanic_app.py - Sanic backend for the semiconductor monitor.

Run:
    python3 sanic_app.py
    (or) sanic sanic_app:app --host 0.0.0.0 --port 8002 --single-process
"""
import asyncio
import os
import json

from sanic import Sanic, response

from core.engine import MonitorEngine
from core.ai_insights import analyze_alert_burst, summarize_shift

engine = MonitorEngine(db_path=os.environ.get("ALERTS_DB_PATH", "alerts_sanic.db"))
app = Sanic("semiconductor_monitor_sanic")


@app.before_server_start
async def start_engine(app):
    engine.start()


@app.after_server_stop
async def stop_engine(app):
    engine.stop()


@app.get("/health")
async def health(request):
    return response.json({"status": "ok", "framework": "sanic"})


@app.get("/alerts")
async def alerts(request):
    limit = int(request.args.get("limit", 50))
    severity = request.args.get("severity")
    return response.json(engine.get_alerts(limit=limit, severity=severity))


@app.get("/alerts/history")
async def alerts_history(request):
    limit = int(request.args.get("limit", 100))
    source = request.args.get("source")
    return response.json(engine.get_history(limit=limit, source=source))


@app.get("/summary")
async def summary(request):
    return response.json(engine.get_summary())


@app.get("/alerts/analyze")
async def analyze(request):
    minutes = float(request.args.get("minutes", 5.0))
    recent = engine.get_recent_window(minutes=minutes)
    return response.json({
        "window_minutes": minutes, "alert_count": len(recent),
        "hypothesis": analyze_alert_burst(recent),
    })


@app.get("/alerts/report")
async def report(request):
    hours = float(request.args.get("hours", 8.0))
    source = request.args.get("source")
    history = engine.get_history_window(hours=hours, source=source)
    return response.json({
        "window_hours": hours, "alert_count": len(history),
        "report": summarize_shift(history, hours),
    })


@app.websocket("/ws/alerts")
async def ws_alerts(request, ws):
    last_id = 0
    while True:
        new = engine.get_new_alerts(last_id)
        if new:
            last_id = new[-1]["id"]
            await ws.send(json.dumps(new))
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002, single_process=True)
