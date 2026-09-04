"""The registry, the CLI and the heartbeat config cannot drift apart.

Each half of this was once silent. The schedule lived as a hand-maintained
string several hundred lines from the commands it described, so a registry entry
with no subcommand produced a cron line pointing at nothing, and a subcommand
with no entry produced a job nobody ever scheduled. Neither fails loudly: the
first fails at 3am in a log nobody reads, and the second never fails at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import PROJECT_ROOT, SCRIPTS_DIR  # noqa: E402
from scripts.reporting.jobs import FIX_POLICIES, JOBS, JOBS_BY_KEY, _allowlisted, crontab_block  # noqa: E402


def _cli_commands():
    from cli.report import report

    return set(report.commands) - {"cron", "watch"}


def test_every_registry_entry_has_a_subcommand():
    missing = {job.key for job in JOBS} - _cli_commands()
    assert not missing, f"Registered with no `{{CLI}} report` subcommand: {sorted(missing)}"


def test_every_subcommand_has_a_registry_entry():
    orphans = _cli_commands() - {job.key for job in JOBS}
    assert not orphans, (
        f"`{{CLI}} report` subcommands with no registry entry: {sorted(orphans)} — "
        "these are commands nobody will ever schedule."
    )


def test_every_job_module_exists():
    missing = [job.key for job in JOBS if not (SCRIPTS_DIR / "reporting" / f"{job.module}.py").exists()]
    assert not missing, f"Jobs whose module file is missing: {missing}"


def test_every_job_has_a_prompt_named_after_its_module():
    """The prompt's filename is how the fix policy is resolved. A prompt named
    anything else is a job whose blast radius nothing can look up."""
    missing = [job.key for job in JOBS if not (SCRIPTS_DIR / "reporting" / "prompts" / f"{job.module}.md").exists()]
    assert not missing, f"Jobs with no prompts/<module>.md: {missing}"


def test_fix_policies_are_known():
    unknown = {job.key: job.fix_policy for job in JOBS if job.fix_policy not in FIX_POLICIES}
    assert not unknown, f"Unknown fix policies: {unknown}. Valid: {sorted(FIX_POLICIES)}"


def test_committing_jobs_do_not_share_a_cron_minute():
    """Only one committing job may be in flight at a time.

    Nearly every job spawns an agent that edits and commits the same tree, and
    several regenerate the same derived docs. Run concurrently they race on git
    and on those files — and the loser's work vanishes with no error.
    """
    seen = {}
    for job in (j for j in JOBS if j.commits):
        minute, hour = job.cron.split()[0], job.cron.split()[1]
        days = job.cron.split()[4]
        key = (minute, hour, days)
        assert key not in seen, (
            f"'{job.key}' and '{seen[key]}' both commit and both fire at {hour}:{minute} on day-spec '{days}'. "
            "They will race on the git tree."
        )
        seen[key] = job.key


def test_heartbeat_vars_are_unique():
    seen = {}
    for job in JOBS:
        if not job.heartbeat_var:
            continue
        assert job.heartbeat_var not in seen, (
            f"'{job.key}' and '{seen[job.heartbeat_var]}' share {job.heartbeat_var} — "
            "one dead job would be masked by the other's ping."
        )
        seen[job.heartbeat_var] = job.key


def test_heartbeat_vars_are_documented_in_env_example():
    """A monitor variable no operator can find is a monitor nobody wires up."""
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [job.heartbeat_var for job in JOBS if job.heartbeat_var and job.heartbeat_var not in env_example]
    assert not missing, f"Heartbeat vars absent from .env.example: {missing}"


def test_allowlisted_jobs_give_a_reason():
    """An unexplained gap in the crontab reads identically to a job that
    silently stopped running. The reason is what distinguishes them."""
    reasonless = [key for key, reason in _allowlisted().items() if not reason]
    assert not reasonless, f"Schedule-allowlist entries with no reason: {reasonless}"


def test_allowlist_names_real_jobs():
    """An entry naming a job that does not exist is a stale exemption.

    The direction with teeth: a job key that leaves the registry and later comes
    back for something else would arrive **pre-exempted from the crontab**, and
    nobody chose that. The job would be registered, documented, and silently
    never scheduled — which is the failure `test_allowlisted_jobs_give_a_reason`
    exists to prevent, arriving through the allowlist instead of past it.
    """
    unknown = set(_allowlisted()) - set(JOBS_BY_KEY)
    assert not unknown, f"Allowlist names jobs that do not exist: {sorted(unknown)} — a stale exemption"


def test_crontab_block_sets_path():
    """cron does not give you your login PATH. A job that works in your shell
    and not under cron is almost always this — and it fails by not finding the
    interpreter, which reads as a broken job rather than a broken PATH."""
    assert "PATH=" in crontab_block()


def test_agent_argv_substitutes_the_prompt():
    """The default invocation carries the prompt as one argument."""
    from scripts.reporting.agent_runner import agent_argv

    argv = agent_argv("PROMPT-BODY")
    assert "PROMPT-BODY" in argv, argv
    assert "{prompt}" not in " ".join(argv)


def test_agent_argv_honours_the_override(monkeypatch):
    from scripts.reporting.agent_runner import AGENT_CMD_VAR, agent_argv

    monkeypatch.setenv(AGENT_CMD_VAR, "some-agent run --yes {prompt}")
    assert agent_argv("BODY") == ["some-agent", "run", "--yes", "BODY"]


def test_agent_argv_refuses_a_template_with_no_prompt(monkeypatch):
    """The failure that looks most like success.

    An agent invoked with no instruction starts, does nothing, and exits 0 — and
    the ledger then records `ok` for a job that was never asked to do anything.
    Refusing here turns that into a decline with a reason.
    """
    from scripts.reporting.agent_runner import AGENT_CMD_VAR, agent_argv

    monkeypatch.setenv(AGENT_CMD_VAR, "some-agent run --yes")
    with pytest.raises(ValueError, match="no .*prompt.* token"):
        agent_argv("BODY")


def test_agent_command_is_documented_for_operators():
    """A knob no operator can find is a knob nobody turns — the same rule the
    heartbeat variables follow."""
    from scripts.reporting.agent_runner import AGENT_CMD_VAR

    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert AGENT_CMD_VAR in env_example
