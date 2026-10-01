import io, logging, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import redact as R


def test_extra_patterns_and_allowlist():
    try:
        R.configure([r"\bBADGE-\d{6}\b", r"\b[a-z0-9-]+\.corp\.example\.com\b"], allowlist=["10.0.0.1"])
        assert R.redact("operator BADGE-123456 logged in") == "operator **** logged in"
        assert R.redact("host db1.corp.example.com down") == "host **** down"
        assert R.redact("gateway 10.0.0.1 and client 10.0.0.2") == "gateway 10.0.0.1 and client ****"
        assert R.redact("api_key=abc 10.0.0.1") == "api_key=**** 10.0.0.1"            # built-ins still apply
    finally:
        R.configure([], [])


def test_invalid_pattern_fails_loudly():
    try:
        R.configure(["(unclosed"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "invalid redaction pattern" in str(e)
    finally:
        R.configure([], [])


def test_log_records_are_masked_including_tracebacks():
    R.install_logging_redaction()
    R.install_logging_redaction()                      # idempotent
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("test.redaction")
    log.addHandler(h); log.setLevel(logging.INFO); log.propagate = False
    log.info("login failed password=%s for %s", "hunter2", "eng@fab.example.com")
    try:
        raise RuntimeError("bad token=abc123secret")
    except RuntimeError:
        log.exception("boom")
    out = buf.getvalue()
    assert "hunter2" not in out and "eng@fab" not in out and "abc123secret" not in out
    assert "password=****" in out and "RuntimeError" in out
