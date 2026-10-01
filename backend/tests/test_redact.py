import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.redact import redact, MASK


def test_api_key_and_kv():
    assert "sk-ant-abc123def456ghi789" not in redact("key sk-ant-abc123def456ghi789 leaked")
    assert redact("api_key=hunter2 rest") == "api_key=**** rest"
    assert redact('password: "p@ss w0rd" ok') == "password: **** ok"
    assert redact("ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx") == "ANTHROPIC_API_KEY=****"


def test_bearer_jwt_url_email_ip():
    assert redact("Authorization: Bearer abc.def-123") == "Authorization: ****"
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk"
    assert redact(f"tok {jwt}") == f"tok {MASK}"
    assert redact("db postgres://admin:s3cret@10.0.0.5:5432/x") == "db postgres://****@****:5432/x"
    assert redact("mail eng@fab.example.com now") == "mail **** now"
    assert redact("host 192.168.1.20 up") == "host **** up"


def test_private_key_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    assert redact("x " + pem + " y") == "x **** y"


def test_normal_alerts_untouched():
    for s in ["Temperature out of range: 98.41",
              "Die #12: FAIL on test 'Leakage_Current' (bin 4)",
              "device log: ERROR NULL_PTR_DEREF at 0x0000A3F1 in task_sensor_poll",
              "Controller CPU usage critical: 93.2%",
              "Low disk space on log volume: 7.5 GB free"]:
        assert redact(s) == s


def test_non_string():
    assert redact(None) is None and redact(5) == 5


def test_shared_vectors_match():
    import json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "shared", "redaction_cases.json")
    for c in json.load(open(path))["cases"]:
        assert redact(c["input"]) == c["expected"], c["input"]


def test_no_catastrophic_backtracking():
    import time
    nasty = ["a" * 200_000, "1." * 100_000, "sk-" + "a" * 200_000, "password=" + "x" * 200_000,
             "a@" * 50_000, "-----BEGIN PRIVATE KEY-----" + "z" * 200_000, "Bearer " + "a" * 200_000]
    for s in nasty:
        t = time.time()
        redact(s)
        assert time.time() - t < 2.0, s[:20]
