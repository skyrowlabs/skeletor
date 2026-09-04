"""The job registry — one source of truth for schedule, identity and autonomy.

Three things are derived from this module and therefore cannot drift apart: the
crontab, the `{{CLI}} report` subcommands, and the status viewer. Before it existed,
the schedule was a hand-maintained string living several hundred lines from the
functions it described, and forgetting one half was silent — a command nobody
schedules, or a cron line pointing at a subcommand that does not exist.

`tests/test_reporting_jobs.py` asserts the registry and the CLI agree in both
directions.

## The grid is load-bearing, not cosmetic

Two rules generate it:

1. **Only one committing job may be in flight at a time.** Nearly every job
   spawns a headless agent that edits and commits the same git tree, and several
   regenerate the same derived docs. Run concurrently, they race on git and on
   those files. Jobs that commit nothing may share a window.

2. **Weekly work is partitioned by weekday, not packed into one night.** A lane
   per weekday, sized at several times the observed run length. The margin is
   the point: a block sized to today's runtime is a bet that runtime never
   grows, and it leaves no room for the next job.

Adjacency within a night is deliberate too — whichever job regenerates a shared
index last wins, so the one whose pass should include the other's edits goes
second.

The nightly spine is a **pipeline**: agents commit, then a gate job checks what
they committed, then a repair job fixes what the gate found, then a digest
reports the night as a closed set. Ordering the heavy agents *after* the gates
would leave every agent commit ungated until the following night.

Stdlib only — imported by host-side jobs that must not grow dependencies.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import allowlist  # noqa: E402
from scripts.paths import PROJECT_ROOT, SCRIPTS_DIR  # noqa: E402

#: Where every cron line appends its raw output. The structured per-run outcome
#: lives in the ledger; this is the transcript.
CRON_LOG = "tmp/reporting/cron.log"

#: Deliberate "do not schedule this" decisions, with reasons.
SCHEDULE_ALLOWLIST = SCRIPTS_DIR / "reporting_schedule_allowlist.yaml"

#: The repo path used in generated crontab lines.
#:
#: Derived, never baked in at scaffold time. A literal absolute path is wrong
#: the moment the repo is cloned or moved somewhere else — and cron fails
#: silently, so nobody finds out until a report stops arriving. It also made
#: `black` red on arrival for anyone whose checkout path was long enough to
#: push the assignment past the line limit.
CRON_CWD = str(PROJECT_ROOT)

#: The timezone every schedule here is expressed in.
#:
#: These describe the HOST's crontab, which fires in the host's local time — so
#: the fire times are local-calendar facts and must not be re-expressed in UTC:
#: they would drift from the cron lines they describe, and drift again by an
#: hour at each DST transition.
#:
#: What they must not be is *implicitly* local. A bare `datetime.now()` means
#: "whatever timezone this machine is in", which is this zone on the host and
#: **UTC** on a CI runner — which is how a whole test file can pass locally and
#: fail in CI for thirteen hours every Saturday. Naming the zone makes the
#: answer identical everywhere, and zoneinfo handles DST.
#:
#: Instants — log stamps, `generated:` fields, staleness — stay UTC and
#: tz-aware. This constant is only for wall-clock schedule arithmetic.
SCHEDULE_TZ = ZoneInfo("{{TZ}}")


def now_local() -> datetime:
    """Now on the schedule clock — naive, and identical on every machine."""
    return datetime.now(SCHEDULE_TZ).replace(tzinfo=None)


#: What a job is allowed to repair without asking.
#:
#: It defaults to `none`, deliberately: a job added without thinking about blast
#: radius gets NO autonomy rather than inheriting whatever the entry above it
#: had. Widening this is a decision, and it should read like one.
FIX_POLICIES = {
    "none": "reports only; never writes to the repo",
    "own-report": "may write and commit its own report file, nothing else",
    "docs": "may repair generated docs and commit them",
    "code": "may open a pull request; never merges, never pushes to a protected branch",
}


@dataclass(frozen=True)
class Job:
    """One scheduled job."""

    key: str  # `{{CLI}} report <key>`
    module: str  # scripts/reporting/<module>.py
    cadence: str  # human-readable, for the docs table
    cron: str  # five cron fields
    writes: str  # what artifact it produces, or "—"
    fix_policy: str = "none"
    commits: bool = False  # does it touch the git tree?
    first_week_only: bool = False  # monthly jobs ride a weekly lane; see below
    heartbeat_var: Optional[str] = None  # env var holding its dead-man-switch URL

    def command(self) -> str:
        return f"cd {CRON_CWD} && ./{{CLI}} report {self.key} >> {CRON_LOG} 2>&1"

    def cron_line(self) -> str:
        return f"{self.cron} {self.command()}"


#: Monthly jobs take a weekly lane plus `first_week_only`, rather than a
#: `0 0 1 * *` schedule. cron ORs day-of-month against day-of-week, so "first
#: Sunday" is not expressible in cron fields at all, and a bare day-of-month
#: schedule lands on a weekly lane one month in seven. The gate is enforced once,
#: in the runner.
def in_first_week(when: Optional[datetime] = None) -> bool:
    return (when or now_local()).day <= 7


#: ONE fully-worked job ships here — registry entry, module, prompt, heartbeat
#: variable — because a registry seeded with entries whose modules do not exist
#: is a registry whose own tests are red on arrival, and a suite people have
#: learned to expect red from has stopped working.
#:
#: Add the rest by copying this shape. `docs/AGENTIC_AUTOMATION.md` § Adding a
#: job lists the five places a new entry touches; `tests/test_reporting_jobs.py`
#: fails if you miss one.
JOBS: List[Job] = [
    Job(
        key="repo-report",
        module="repo_report",
        cadence="Sat 22:00",
        cron="0 22 * * 6",
        writes="docs/reports/regular/repository-report.md",
        fix_policy="own-report",
        commits=True,
        heartbeat_var="HEARTBEAT_REPO_REPORT",
    ),
]

JOBS_BY_KEY: Dict[str, Job] = {job.key: job for job in JOBS}


def _allowlisted() -> Dict[str, str]:
    """Jobs deliberately registered but NOT scheduled, with their reasons.

    Read through `scripts/allowlist.py`, the one reader every allowlist in this
    repository shares. There were four copies of this parsing and they drifted.
    """
    return allowlist.read(SCHEDULE_ALLOWLIST)


def crontab_block() -> str:
    """The crontab block, generated. Never hand-copy this into `crontab -e`
    from the docs — the registry is the system; the docs table is documentation
    of it, and only one of the two can be wrong without anybody noticing."""
    exempt = _allowlisted()
    lines = [
        "# ── BEGIN generated by `{{CLI}} report cron --print` ──",
        "# Do not hand-edit. Regenerate after any change to scripts/reporting/jobs.py.",
        f"SHELL=/bin/bash",
        # cron does not give you your login PATH. A job that works in your shell
        # and not under cron is almost always this, and it fails by not finding
        # the interpreter — which reads as a broken job rather than a broken PATH.
        f"PATH={os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}",
        "",
    ]
    for job in JOBS:
        if job.key in exempt:
            lines.append(f"# {job.key}: OFF — {exempt[job.key]}")
            continue
        lines.append(f"# {job.key} — {job.cadence} — {job.writes}")
        lines.append(job.cron_line())
    lines.append("# ── END generated ──")
    return "\n".join(lines) + "\n"
