"""
ai_insights.py - LLM-powered root-cause hypotheses and shift summaries.

Two features, both using the Anthropic API:

  1. analyze_alert_burst(alerts) - given a short burst of recent alerts
     across subsystems (FAB/ATE/FIRMWARE/HEALTH), ask Claude whether they
     look related and what the likely shared root cause is.
  2. summarize_shift(alerts, hours) - turn a longer stretch of alert
     history into a short shift-handoff report.

Requires the ANTHROPIC_API_KEY environment variable. If it isn't set, or
the 'anthropic' package isn't installed, both functions return a clear
message instead of raising -- callers can surface that message directly
in an API response rather than a 500 error.
"""

import os
from typing import Dict, List, Optional, Tuple

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only if the package is missing
    anthropic = None

MODEL = "claude-sonnet-5"


def _get_client() -> Tuple[Optional["anthropic.Anthropic"], Optional[str]]:
    if anthropic is None:
        return None, "The 'anthropic' package is not installed. Run: pip install anthropic"
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY environment variable is not set."
    return anthropic.Anthropic(api_key=api_key), None


def _format_alerts(alerts: List[Dict]) -> str:
    return "\n".join(
        f"- [{a['timestamp']}] {a['source']}/{a['severity']}: {a['message']}"
        for a in alerts
    )


def analyze_alert_burst(alerts: List[Dict]) -> str:
    """
    Given recent alert dicts (id, timestamp, source, severity, message),
    return a short plain-English root-cause hypothesis.
    """
    client, error = _get_client()
    if error:
        return f"AI analysis unavailable: {error}"
    if not alerts:
        return "No recent alerts to analyze."

    prompt = (
        "You are helping a semiconductor fab engineer triage a burst of "
        "monitoring alerts from different subsystems (FAB sensors, ATE test "
        "equipment, FIRMWARE device logs, system HEALTH). Given the alerts "
        "below, in 3-5 sentences: (1) say whether they look related or "
        "coincidental, (2) give your single best hypothesis for a shared "
        "root cause if one is plausible, and (3) suggest one concrete next "
        "diagnostic step. Be direct and concise. If there truly isn't enough "
        "information to hypothesize, say so plainly instead of guessing.\n\n"
        f"Alerts:\n{_format_alerts(alerts)}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as e:
        return f"AI analysis failed: {e}"


def summarize_shift(alerts: List[Dict], hours: float) -> str:
    """
    Summarize a longer stretch of alert history into a short shift-handoff
    report for the next engineer.
    """
    client, error = _get_client()
    if error:
        return f"AI summary unavailable: {error}"
    if not alerts:
        return f"No alerts recorded in the last {hours:.0f} hours."

    prompt = (
        f"Summarize the following {len(alerts)} monitoring alerts from the "
        f"last {hours:.0f} hours of a semiconductor fab/test floor into a "
        "short shift-handoff report for the next engineer. Structure it as: "
        "1) Overall status (one line), 2) Notable incidents by subsystem "
        "(FAB/ATE/FIRMWARE/HEALTH), 3) Anything that needs follow-up. "
        f"Keep it under 200 words.\n\nAlerts:\n{_format_alerts(alerts)}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as e:
        return f"AI summary failed: {e}"
