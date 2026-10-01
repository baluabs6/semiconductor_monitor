"""
redact.py - masks sensitive data with ****.

Applied at every boundary where free text could leak a secret:
  * engine._emit()        -> before an alert is buffered, persisted (SQLite),
                             served by the REST API or pushed over WebSocket
  * ai_insights           -> before alert text is sent to the LLM, and on any
                             error text returned to the caller
  * python/monitor.py     -> before console output and alerts.log

What is masked:
  private key blocks, JWTs, credentials embedded in URLs, Bearer tokens,
  values of key=value / key: value secrets (api_key, token, password, secret,
  authorization, ...), sk-... API keys, AWS access key IDs, e-mail addresses,
  IPv4 addresses.

Pattern-based masking is a safety net, not a guarantee: a secret with no
recognisable shape or label can still get through. Do not log secrets on purpose.
"""

import re

MASK = "****"
MAX_INPUT_CHARS = 50_000  # alerts are short; bounding input bounds regex work (DoS guard)

_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"

_PATTERNS = [
    # (compiled regex, replacement)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), MASK),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), MASK),           # JWT
    (re.compile(r"(?<=://)[^\s/@:]+:[^\s/@]+(?=@)"), MASK),                                        # scheme://user:pass@host
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer " + MASK),
    (re.compile(
        r"(?i)\b(api[_-]?key|apikey|secret(?:[_-]?key)?|token|password|passwd|pwd|"
        r"authorization|access[_-]?key|private[_-]?key|client[_-]?secret)\b"
        r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;\"']+)"),
     lambda m: f"{m.group(1)}{m.group(2)}{MASK}"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), MASK),                                                # sk-ant-..., sk-...
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), MASK),                                           # AWS key id
    (re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+"), MASK),                  # e-mail
    (re.compile(rf"\b{_OCTET}(?:\.{_OCTET}){{3}}\b"), MASK),                                        # IPv4
]


def redact(text):
    """Return `text` with sensitive values replaced by ****. Non-strings are returned unchanged."""
    if not isinstance(text, str) or not text:
        return text
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "...[truncated]"
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text
