"""
backtest_detector.py - measures the C++ anomaly detector on synthetic data with labeled faults.

Reports, per severity, detection rate (recall) and false-positive rate, plus detection of
faults that arrive while an earlier fault is still inside the rolling window ("masked" faults).

Run (after ./build.sh):   python3 backend/tests/backtest_detector.py [--samples 200000] [--seed 7]
Exit code is non-zero if quality gates fail, so it can run in CI.
"""
import argparse
import ctypes
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.engine import load_libraries  # noqa: E402

MEAN, SIGMA = 70.0, 2.0


def run(samples: int, seed: int, fault_rate: float, magnitude_sigma: tuple):
    _, anomaly = load_libraries()
    anomaly.init_engine(50)
    rng = random.Random(seed)
    sev = ctypes.c_int(0)

    tp = fn = fp = tn = 0
    crit_hits = 0
    masked_tp = masked_total = 0
    since_fault = 10**9
    for _ in range(samples):
        is_fault = rng.random() < fault_rate
        if is_fault:
            value = MEAN + rng.choice([-1, 1]) * rng.uniform(*magnitude_sigma) * SIGMA
        else:
            value = rng.gauss(MEAN, SIGMA)
        flagged = anomaly.check_anomaly(0, ctypes.c_float(value), 3.0, 5.0, ctypes.byref(sev))
        masked = is_fault and since_fault < 50  # an earlier fault is still in the window
        if is_fault:
            if flagged:
                tp += 1
                crit_hits += 1 if sev.value == 2 else 0
            else:
                fn += 1
            masked_total += 1 if masked else 0
            masked_tp += 1 if (masked and flagged) else 0
            since_fault = 0
        else:
            fp += 1 if flagged else 0
            tn += 0 if flagged else 1
            since_fault += 1
    return {
        "recall": tp / max(tp + fn, 1),
        "critical_share_of_hits": crit_hits / max(tp, 1),
        "false_positive_rate": fp / max(fp + tn, 1),
        "masked_recall": masked_tp / max(masked_total, 1),
        "faults": tp + fn,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    # 8% is the engine's default injected-fault rate; 15-40 sigma-equivalents are large, obvious faults
    result = run(a.samples, a.seed, fault_rate=0.08, magnitude_sigma=(8.0, 20.0))
    for k, v in result.items():
        print(f"{k:>24}: {v:.4f}" if isinstance(v, float) else f"{k:>24}: {v}")

    gates = [
        ("recall >= 0.99", result["recall"] >= 0.99),
        ("false_positive_rate <= 0.01", result["false_positive_rate"] <= 0.01),
        ("masked_recall >= 0.99", result["masked_recall"] >= 0.99),
    ]
    ok = True
    for name, passed in gates:
        print(("PASS " if passed else "FAIL ") + name)
        ok &= passed
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
