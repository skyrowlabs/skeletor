#!/usr/bin/env python3
"""`skel report maintain`: skeletor's weekly pass, `bin/skeletor-maintain --agent`.

That tool asks its cheap questions first (CI, pins, upstream) and wakes an agent
only when one finds work, so this job has no agent stage of its own and records
`ok` on a clean run. docs/MAINTENANCE.md is the procedure; this is its schedule.
The agent runs as the resolved seat, like every agent the registry starts.
skeletor's own job: it lives in this tree, never in template/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.paths import PROJECT_ROOT  # noqa: E402
from scripts.reporting import agent_runner, run_ledger, shellout  # noqa: E402
from scripts.reporting.jobs import JOBS_BY_KEY  # noqa: E402

KEY = "maintain"


def main() -> int:
    job = JOBS_BY_KEY[KEY]
    started = run_ledger.now()
    argv = [str(PROJECT_ROOT / "bin" / "skeletor-maintain"), "--agent"]
    if agent_runner.dry_run():
        argv.append("--dry-run")
    done = shellout.run(argv, cwd=str(PROJECT_ROOT), env=agent_runner.agent_env(KEY))
    if agent_runner.dry_run():
        return done.returncode
    outcome = "ok" if done.returncode == 0 else "failed"
    reason = "" if outcome == "ok" else f"bin/skeletor-maintain exited {done.returncode}; the cron log has its output"
    branch = agent_runner.current_branch() or ""
    run_ledger.record(
        run_ledger.Run(
            job=KEY, outcome=outcome, started=started, finished=run_ledger.now(), branch=branch, reason=reason
        )
    )
    agent_runner.heartbeat(os.environ.get(job.heartbeat_var or ""), "up" if outcome == "ok" else "down")
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
