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

import json
import logging
import os
import re
import traceback

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


_extra = []       # compiled extra patterns (configured)
_allow = []       # literal strings that must never be masked (configured)


def configure(extra_patterns=None, allowlist=None):
    """
    Add organisation-specific masking rules.
      extra_patterns: regex strings, e.g. [r"\\bBADGE-\\d{6}\\b", r"\\b[a-z0-9-]+\\.corp\\.example\\.com\\b"]
      allowlist:      literal strings that are left alone (cuts false positives, e.g. a public gateway IP)
    An invalid regex raises ValueError: silently ignoring it would leave data unmasked.
    Env at import time: REDACT_EXTRA_PATTERNS and REDACT_ALLOWLIST (JSON lists of strings).
    """
    global _extra, _allow
    compiled = []
    for pat in extra_patterns or []:
        try:
            compiled.append(re.compile(pat))
        except re.error as e:
            raise ValueError(f"invalid redaction pattern {pat!r}: {e}") from None
    _extra = compiled
    _allow = [a for a in (allowlist or []) if a]


def _configure_from_env():
    def _load(name):
        raw = os.environ.get(name, "").strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{name} must be a JSON list of strings: {e}") from None
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{name} must be a JSON list of strings")
        return value
    configure(_load("REDACT_EXTRA_PATTERNS"), _load("REDACT_ALLOWLIST"))


def redact(text):
    """Return `text` with sensitive values replaced by ****. Non-strings are returned unchanged."""
    if not isinstance(text, str) or not text:
        return text
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "...[truncated]"
    # protect allow-listed literals from every rule, then restore them
    protected = {}
    for i, literal in enumerate(_allow):
        if literal in text:
            token = f"\x00ALLOW{i}\x00"
            protected[token] = literal
            text = text.replace(literal, token)
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    for pattern in _extra:
        text = pattern.sub(MASK, text)
    for token, literal in protected.items():
        text = text.replace(token, literal)
    return text


def install_logging_redaction():
    """
    Mask secrets in EVERY log record (message and traceback) from any logger/handler, including
    uvicorn, Sanic and third-party libraries. Idempotent. Call once at application start-up.
    """
    if getattr(logging, "_monitor_redaction_installed", False):
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        try:
            record.msg = redact(record.getMessage())
            record.args = None
            if record.exc_info and record.exc_info[0] is not None:
                record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)).rstrip())
        except Exception:                      # never let masking break logging
            pass
        return record

    logging.setLogRecordFactory(factory)
    logging._monitor_redaction_installed = True


_configure_from_env()
