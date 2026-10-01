"""
genealogy.py - which lot / wafer / recipe / step was on the tool when something happened.

LotTracker records lot runs on one tool (start/end per lot) and hands out the current context, which
the engine stamps onto every alert. That is what makes excursion containment possible: "which lots
were exposed while the chamber was out of range?"

The lot feed is SIMULATED here (lots advance on a timer). In production, feed start_lot()/end of run
from your MES / equipment events (SECS/GEM) instead; nothing else changes.
"""

import itertools
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional

STEPS = ["PREHEAT", "DEPOSIT", "ETCH", "COOLDOWN"]
WAFERS_PER_LOT = 25


@dataclass
class LotRun:
    lot_id: str
    tool_id: str
    recipe: str
    start: str                  # ISO timestamp
    end: Optional[str] = None   # None while the lot is still running

    def as_dict(self) -> Dict:
        return asdict(self)


class LotTracker:
    def __init__(self, tool_id: str = "TOOL-01", first_lot: str = "LOT-0000", recipe: str = "RCP-A"):
        self.tool_id = tool_id
        self._lock = threading.Lock()
        self._runs: List[LotRun] = []
        self._wafer = 0
        self._step_i = 0
        self._seq = itertools.count(1)
        self.start_lot(first_lot, recipe)

    @staticmethod
    def _now(now: Optional[datetime]) -> datetime:
        return now or datetime.now()

    def next_lot_id(self, now: Optional[datetime] = None) -> str:
        return f"LOT-{self._now(now).strftime('%Y%m%d')}-{next(self._seq):04d}"

    def start_lot(self, lot_id: str, recipe: str, now: Optional[datetime] = None) -> LotRun:
        ts = self._now(now).isoformat(timespec="milliseconds")
        with self._lock:
            if self._runs and self._runs[-1].end is None:
                self._runs[-1].end = ts
            run = LotRun(lot_id=lot_id, tool_id=self.tool_id, recipe=recipe, start=ts)
            self._runs.append(run)
            self._runs = self._runs[-500:]          # bounded memory
            self._wafer = 0
            self._step_i = 0
            return run

    def advance(self):
        """Move to the next wafer / process step (called by the simulator loop)."""
        with self._lock:
            self._step_i = (self._step_i + 1) % len(STEPS)
            if self._step_i == 0:
                self._wafer = self._wafer % WAFERS_PER_LOT + 1

    def current_context(self) -> Dict[str, str]:
        with self._lock:
            run = self._runs[-1]
            return {"tool_id": self.tool_id, "lot_id": run.lot_id, "wafer_id": f"WF-{max(self._wafer, 1):02d}",
                    "recipe": run.recipe, "step": STEPS[self._step_i]}

    def runs(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return [r.as_dict() for r in self._runs[-limit:]][::-1]       # newest first

    def runs_overlapping(self, t0: datetime, t1: datetime) -> List[LotRun]:
        """Lot runs whose [start, end] overlaps [t0, t1]; a run still in progress counts as open-ended."""
        out = []
        with self._lock:
            for r in self._runs:
                start = datetime.fromisoformat(r.start)
                end = datetime.fromisoformat(r.end) if r.end else datetime.max
                if start <= t1 and end >= t0:
                    out.append(LotRun(**asdict(r)))
        return out
