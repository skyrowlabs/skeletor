"""``{{CLI}} test`` — marker-driven suite selection.

Every suite here maps to exactly one pytest marker, and a test file joins a
suite by declaring that marker. There is **no registry**: no per-suite file
list, no CI step per feature, nothing to forget to update.
"""

from __future__ import annotations

import os
import sys

import click

from cli.helpers import PROJECT_ROOT, run, shell, skip, step, summarize

#: pytest's exit code for "the marker you asked for selected nothing".
NO_TESTS_COLLECTED = 5

#: marker -> (help text, whether the suite needs the stack running)
SUITES = {
    "unit": ("host-side tests, no services required", False),
    "integration": ("requires the stack up and seeded", True),
    "manual": ("never in scheduled CI — E2E, live third-party, paid APIs", True),
}


def _pytest(marker: str, extra: tuple, ci: bool) -> int:
    env_note = " (CI semantics: env-gate skips become failures)" if ci else ""
    step(f"{marker} suite{env_note}")
    env = dict(os.environ)
    if ci:
        # Under CI semantics an env-gate skip is a harness failure, not a pass:
        # CI guarantees the environment, so "skipped everything" must be red.
        env["{{CI_ENV_VAR}}"] = "1"
    cmd = [sys.executable, "-m", "pytest", "tests/", "-m", marker, "-q", "--durations=10", *extra]
    shell(" ".join(cmd))
    import subprocess

    code = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env).returncode

    # A suite that needs the stack is one this project has not written a test
    # for yet, and pytest calls an empty selection an ERROR. So a fresh tree is
    # red the first time anybody runs it or CI does — and a first check that is
    # red is how a team learns that red is normal.
    #
    # Reported as empty, never as a pass, and never for `unit`: tests ship for
    # that one, so nothing collected there means the harness is broken.
    if code == NO_TESTS_COLLECTED and SUITES[marker][1]:
        skip(f"no {marker} tests are marked yet — the suite is empty, not passing")
        return 0
    return code


@click.group(invoke_without_command=True)
@click.pass_context
def test(ctx: click.Context) -> None:
    """Run a test suite by marker."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _make(marker: str, description: str):
    @click.option("--ci", is_flag=True, help="reproduce CI's skip semantics (skips become failures)")
    @click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
    def command(ci: bool, pytest_args: tuple) -> None:
        sys.exit(_pytest(marker, pytest_args, ci))

    command.__doc__ = description
    command.__name__ = marker
    return click.command(name=marker, context_settings={"ignore_unknown_options": True})(command)


for _marker, (_desc, _needs_stack) in SUITES.items():
    test.add_command(_make(_marker, _desc))


@test.command()
@click.option("--ci", is_flag=True, help="reproduce CI's skip semantics")
def all(ci: bool) -> None:
    """Every suite except `manual`, in cost order."""
    results = [(marker, _pytest(marker, (), ci)) for marker in SUITES if marker != "manual"]
    sys.exit(summarize(results))


@test.command()
@click.option("-w", "--worst", default=20, show_default=True, help="how many modules to list")
def coverage(worst: int) -> None:
    """Measure coverage and list the worst-covered modules.

    The list is the point: it tells you where a new test buys the most, which is
    a better question than "what is the number".
    """
    code = run(
        [sys.executable, "-m", "pytest", "tests/", "-m", "unit", "-q", "--cov", "--cov-report=term-missing"]
    ).returncode
    if code == 0:
        run([sys.executable, "scripts/check_coverage_budget.py"])
    sys.exit(code)
