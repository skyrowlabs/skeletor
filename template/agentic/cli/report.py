"""``{{CLI}} report`` — the scheduled-job surface.

Every subcommand here has a matching entry in ``scripts/reporting/jobs.py``, and
every entry there has a subcommand. ``tests/test_reporting_jobs.py`` asserts both
directions: a command nobody schedules and a cron line pointing at a command
that does not exist are both silent failures, and each has happened.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import click

from cli.helpers import PROJECT_ROOT, fail, ok, warn

sys.path.insert(0, str(PROJECT_ROOT))


@click.group()
def report() -> None:
    """Scheduled self-maintenance jobs."""


def _run_module(job_key: str) -> None:
    from scripts.reporting.jobs import JOBS_BY_KEY, in_first_week

    job = JOBS_BY_KEY[job_key]

    # Monthly jobs ride a weekly lane because cron ORs day-of-month against
    # day-of-week, so "first Sunday" is not expressible in cron fields. The gate
    # is enforced HERE, once, rather than in each monthly job.
    if job.first_week_only and not in_first_week():
        print(f"⏸️  {job_key}: monthly job, not the first week — skipping")
        sys.exit(0)

    module = importlib.import_module(f"scripts.reporting.{job.module}")
    sys.exit(module.main())


def _register() -> None:
    """Generate one subcommand per registry entry.

    Generated rather than hand-written on purpose: a hand-written list is a
    second registry, and the drift between two registries is exactly what this
    module exists to make impossible.
    """
    from scripts.reporting.jobs import JOBS

    for job in JOBS:
        def make(key: str, cadence: str, writes: str):
            @click.command(name=key, help=f"{cadence} — writes {writes}")
            def command() -> None:
                _run_module(key)

            return command

        report.add_command(make(job.key, job.cadence, job.writes))


_register()


@report.command()
@click.option("--print", "print_", is_flag=True, help="emit the block for `crontab -e`")
@click.option("--check", "check_", is_flag=True, help="does the LIVE crontab match the registry?")
def cron(print_: bool, check_: bool) -> None:
    """The crontab, generated from the registry."""
    from scripts.reporting.jobs import JOBS, _allowlisted, crontab_block

    if print_:
        click.echo(crontab_block())
        return

    if not check_:
        click.echo(crontab_block())
        return

    live = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    exempt = _allowlisted()
    missing, off = [], []
    for job in JOBS:
        if job.key in exempt:
            off.append(f"{job.key}: off (intentional) — {exempt[job.key]}")
            continue
        if f"report {job.key}" not in live:
            missing.append(job.key)

    for line in off:
        print(f"⏸️  {line}")

    if missing:
        fail(f"{len(missing)} registered job(s) are not in the live crontab: {', '.join(missing)}")
        print("\n   'Registered' is not 'installed'. Reinstall with:")
        print("     {{CLI}} report cron --print | crontab -")
        print("\n   If a job is deliberately off, give it a reason in")
        print("   scripts/reporting_schedule_allowlist.yaml — an unexplained gap reads")
        print("   identically to a job that silently stopped running.")
        sys.exit(1)

    ok(f"the live crontab matches the registry ({len(JOBS) - len(off)} scheduled, {len(off)} intentionally off)")


@report.command()
@click.option("-n", "--limit", default=20, show_default=True)
def watch(limit: int) -> None:
    """Recent runs as a timeline: what ran, what it decided, and what it wrote."""
    from scripts.reporting import run_ledger
    from scripts.reporting.jobs import JOBS

    entries = run_ledger.recent(limit)
    if not entries:
        warn("no runs recorded yet")
        return

    badge = {"ok": "✅", "failed": "❌", "declined": "⏸️ ", "skipped": "⏭️ "}
    for entry in entries:
        line = f"{badge.get(entry['outcome'], '?')} {entry['started']}  {entry['job']:<16}"
        if entry.get("committed"):
            line += f"  → {entry['committed']}"
        if entry.get("reason"):
            line += f"  ({entry['reason'][:80]})"
        print(line)

    print()
    for job in JOBS:
        last = run_ledger.last_run(job.key)
        if last is None:
            warn(f"{job.key} has never run — scheduled {job.cadence}")
