import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.promptsafety import sanitize_untrusted
from core.ai_insights import _format_alerts

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _corpus():
    return json.load(open(os.path.join(ROOT, "shared", "injection_corpus.json")))["lines"]


def test_corpus_cannot_break_out_of_the_prompt_structure():
    for line in _corpus():
        out = sanitize_untrusted(line)
        assert "\n" not in out and "\r" not in out, line
        assert "<" not in out and ">" not in out, line
        assert len(out) <= 500 + len("...[truncated]")
        assert all(ord(c) >= 32 for c in out)


def test_formatted_prompt_has_exactly_one_line_per_alert():
    alerts = [{"id": i, "timestamp": "2026-10-01T10:00:00", "source": "FIRMWARE", "severity": "WARNING",
               "message": line} for i, line in enumerate(_corpus())]
    formatted = _format_alerts(alerts)
    assert len(formatted.split("\n")) == len(alerts)       # no line can forge extra entries
    assert "</alerts>" not in formatted


def test_shared_vectors_match():
    cases = json.load(open(os.path.join(ROOT, "shared", "promptsafety_cases.json")))["cases"]
    for c in cases:
        assert sanitize_untrusted(c["input"]) == c["expected"], c["input"]
