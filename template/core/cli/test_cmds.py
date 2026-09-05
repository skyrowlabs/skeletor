"""``{{CLI}} test`` — marker-driven suite selection.

Every suite here maps to exactly one pytest marker, and a test file joins a
suite by declaring that marker. There is **no registry**: no per-suite file
list, no CI step per feature, nothing to forget to update.
"""

from __future__ import annotations

import os
import sys
from typing import NamedTuple

import click

from cli.helpers import PROJECT_ROOT, run, shell, skip, step, summarize

#: pytest's exit code for "the marker you asked for selected nothing".
NO_TESTS_COLLECTED = 5


class Suite(NamedTuple):
    """One row of the suite table, and the two questions a row has to answer.

    They were one boolean — "needs the stack" — read for both, which worked only
    because the three original rows happened to agree on them. `ui` broke that
    the moment it arrived: a Textual pilot needs no stack at all, and the row
    was set `True` anyway to buy the empty-suite tolerance. A right behaviour
    from a wrong value is a value the next reader will trust.
    """

    #: `{{CLI}} test <marker> --help`.
    help: str
    #: Does a fresh scaffold ship tests carrying this marker? If not, an empty
    #: selection is REPORTED rather than failed — pytest calls it exit 5, and a
    #: scaffold that is red the first time anybody runs it teaches a team that
    #: red is normal. `unit` gets no such tolerance: tests ship for it, so
    #: nothing collected there means the harness is broken.
    ships_tests: bool = False
    #: Do the automatic runs — CI, and `{{CLI}} test all` — include this suite?
    #: False buys an exemption from `tests/test_ci_runs_every_suite.py`, which
    #: otherwise requires a workflow here to select every marker this file
    #: offers.
    #:
    #: Both fields default to the answer that is safe to get wrong, which is
    #: what makes them defaults rather than a question quietly skipped. Omit
    #: this one and the new suite is OBLIGED to have a job, so forgetting is a
    #: red gate naming the marker; write `scheduled=False` and you have made a
    #: claim somebody can read. The other direction — a suite CI ignores by
    #: default — is the silent hole this whole file exists to close.
    scheduled: bool = True


#: The suites, and the whole of the table. A test file joins one by declaring
#: the marker; nothing here is a file list.
SUITES = {
    "unit": Suite("host-side tests, no services required", ships_tests=True),
    "integration": Suite("requires the stack up and seeded"),
    # Costs money or needs a person. The one row CI is not expected to run, and
    # the reason that is a field rather than an `if marker != "manual"` in two
    # places, which is what it used to be.
    "manual": Suite("never in scheduled CI — E2E, live third-party, paid APIs", scheduled=False),
    # Empty in a headless tree and that is fine — an empty suite is green, and
    # the row costs nothing until something fills it. It exists as a row rather
    # than as a `--ui` overlay because what a TUI, a browser and an Electron
    # window share is not a framework, it is a failure mode: the interaction can
    # be delivered to nothing. See docs/rules/testing.md § Interaction.
    #
    # `scheduled=True`, and the CI job it obliges is deliberate. The alternative
    # — call `ui` a suite CI cannot run — is false for at least one of the three
    # stacks it names: Textual's pilot is headless and runs on a bare runner. It
    # was also the shipped state, and proto.pilot found what that costs. Their
    # 36 pilot tests match this description word for word, and adopting the
    # marker as written would have deselected every one of them from the unit
    # job with no job left to select them: green over a smaller set, nothing red
    # at any point. A browser or an Electron window may still need a display,
    # and that setup is the adopting repo's — a job failing loudly for want of
    # one is strictly better than tests quietly leaving CI.
    "ui": Suite("drives a user interface; needs a display, a browser, or a pilot"),
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

    # A suite a scaffold ships no tests for selects nothing, and pytest calls an
    # empty selection an ERROR. So a fresh tree would be red the first time
    # anybody runs it or CI does — and a first check that is red is how a team
    # learns that red is normal.
    #
    # Reported as empty, never as a pass, and never for a suite whose tests
    # ship: nothing collected there means the harness is broken.
    if code == NO_TESTS_COLLECTED and not SUITES[marker].ships_tests:
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


for _marker, _suite in SUITES.items():
    test.add_command(_make(_marker, _suite.help))


@test.command()
@click.option("--ci", is_flag=True, help="reproduce CI's skip semantics")
def all(ci: bool) -> None:
    """Every scheduled suite, in cost order.

    Read from the registry rather than excluding `manual` by name, which is the
    same question CI asks and was the same literal written twice.
    """
    results = [(m, _pytest(m, (), ci)) for m, suite in SUITES.items() if suite.scheduled]
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
