"""The structured record of what each scheduled run decided.

Distinct from the cron log, which is a transcript. This answers "did the 03:15
job run last night, and what did it conclude" without anybody reading output —
which is the only question that scales past about five jobs.

Two rails it exists to hold, both of which were once silent:

* **A job whose agent never ran must not report `ok`.** A collection stage that
  succeeds and a triage stage that never started look identical from outside,
  and the second is a job that has quietly stopped working.
* **A red gate may not report `ok`.** A job that finds a problem and records
  success has inverted its own purpose.

Stdlib only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.paths import state_dir  # noqa: E402


def ledger_path() -> Path:
    """Where the run ledger lives — resolved, never spelled out.

    A call rather than a module constant so the environment override still
    works when a test sets it in a fixture: a constant would have frozen the
    answer at import. The root, and the name of that knob, are
    `scripts/paths.py::state_dir`'s to state — not this module's.
    """
    return state_dir("ledger", "ledger.jsonl")


#: Terminal states. `declined` is NOT a failure: a job that correctly chose not
#: to answer (the tree was on the wrong branch, a queue was not quiet) executed
#: properly. It must stay distinguishable from a dead cron, which is why it
#: still pings its heartbeat.
OUTCOMES = ("ok", "failed", "declined", "skipped")


@dataclass
class Run:
    job: str
    outcome: str
    started: str
    finished: str
    branch: str
    agent_ran: bool = False
    committed: Optional[str] = None  # sha, if it wrote anything
    findings: int = 0
    reason: str = ""  # required for declined/failed

    def validate(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome '{self.outcome}' (expected one of {OUTCOMES})")
        # The two rails. Both are asserted here rather than in each job, so a
        # new job cannot forget them.
        if self.outcome == "ok" and not self.agent_ran:
            raise ValueError(
                f"{self.job}: recorded 'ok' but its agent never ran. A collection stage that "
                "succeeded and a triage stage that never started look identical from outside — "
                "record 'failed' with a reason."
            )
        if self.outcome == "ok" and self.findings and not self.committed:
            raise ValueError(
                f"{self.job}: recorded 'ok' with {self.findings} finding(s) and no artifact. "
                "A job that finds a problem and reports success has inverted its own purpose."
            )
        if self.outcome in ("declined", "failed") and not self.reason:
            raise ValueError(f"{self.job}: '{self.outcome}' requires a reason — a verdict with no reason is unreadable")


def record(run: Run) -> None:
    run.validate()
    ledger = ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(run)) + "\n")


def recent(limit: int = 50) -> List[dict]:
    ledger = ledger_path()
    if not ledger.exists():
        return []
    lines = ledger.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_run(job: str) -> Optional[dict]:
    for entry in reversed(recent(500)):
        if entry.get("job") == job:
            return entry
    return None


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
