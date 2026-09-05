"""Every suite the CLI offers is selected by some CI job.

A marker is how a test file joins a suite, and it is also how a test file
*leaves CI*. Those are the same act, and only one of them is visible:

> **Marking a test with a marker no workflow selects deletes it from CI.** The
> unit job runs `-m unit` and deselects it; nothing else selects it; every
> check reports green over a smaller set. Nothing is red at any point, and no
> output anywhere distinguishes the smaller set from the whole one.

That shipped. `ui` was added to `cli/test_cmds.py` with a row, a CLI command
and a documented description, and no job in `.github/workflows/` ran `-m ui`.
proto.pilot adopted the marker holding 36 Textual pilot tests that match its
description word for word; using it as documented would have dropped all 36
from every run they do.

The obligation is a field on the row — `Suite.scheduled` — rather than a list
here, so the exemption for `manual` is the one place somebody adding a suite is
already looking. This file is what makes the field mean something.

## Why the workflows are read with comments blanked

Because a workflow missing a job is the most likely place on earth to find a
comment naming that job. `# SCAFFOLD: add a -m ui step here` satisfies a
substring check perfectly, and the false pass is then *perfectly correlated*
with the defect. `scripts/yaml_text.py` owns the masking; two checks in this
tree learned it the expensive way.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.test_cmds import SUITES  # noqa: E402
from scanning import scanned  # noqa: E402
from scripts.paths import GITHUB_DIR  # noqa: E402
from scripts.yaml_text import read_uncommented  # noqa: E402

WORKFLOWS = GITHUB_DIR / "workflows"

#: A marker expression, as it appears after `pytest` on a command line. The
#: anchor is `pytest` and not the start of the line, because every invocation
#: here is `python -m pytest ...` — matching `-m` anywhere would read python's
#: own module flag and conclude the tree runs a suite called `pytest`.
_SELECTION = re.compile(r"""-m\s+(?:"([^"]*)"|'([^']*)'|([^\s"']+))""")

#: `-m "unit or integration"` selects two suites. Splitting on the boolean
#: vocabulary is enough to name them; this is not an expression evaluator, and
#: does not need to be — an over-broad read here can only make the check more
#: permissive about a marker that IS mentioned, never invent one that is not.
_OPERATORS = re.compile(r"[()]|\b(?:or|and|not)\b")


def selections(text: str) -> set:
    """Every marker named in a pytest selection in `text`."""
    found = set()
    for line in text.splitlines():
        _, sep, tail = line.partition("pytest")
        if not sep:
            continue
        for match in _SELECTION.finditer(tail):
            expression = next(g for g in match.groups() if g is not None)
            found.update(part for part in _OPERATORS.split(expression) if part and part.strip())
    return {marker.strip() for marker in found}


def selected_markers() -> dict:
    """marker -> the workflow files that select it."""
    files = scanned(sorted(WORKFLOWS.glob("*.yml")), "workflow files", least=2)
    where: dict = {}
    for path in files:
        for marker in selections(read_uncommented(path)):
            where.setdefault(marker, []).append(path.name)
    return where


def test_the_scan_reads_real_selections():
    """The extractor is validated against a selection that certainly exists.

    A parser that matched nothing would make every assertion below vacuous, and
    `unit` is the one suite this tree definitely ships tests for and definitely
    runs. If this fails, the regexes are wrong and the rest of the file is
    reporting on an empty set rather than on the workflows.
    """
    found = scanned(selected_markers(), "markers selected by a workflow", least=1)

    assert "unit" in found, (
        "no workflow appears to select `-m unit`, which cannot be true — the extractor is broken, "
        f"so every other assertion here is vacuous. Found: {sorted(found)}"
    )
    assert "pytest" not in found, "the extractor read `python -m pytest` as a marker selection"


def test_every_scheduled_suite_is_run_by_a_workflow():
    obliged = scanned(
        {marker for marker, suite in SUITES.items() if suite.scheduled},
        "suites declaring scheduled=True",
        least=1,
    )
    missing = sorted(obliged - set(selected_markers()))

    assert not missing, (
        f"`cli/test_cmds.py` offers {missing} and no workflow in .github/workflows/ selects them. "
        "A test marked with one is DESELECTED by every job that runs and selected by none, so it "
        "leaves CI silently and every check stays green over the smaller set. Either add a job "
        "that runs it, or set `scheduled=False` on the row and say why."
    )


def test_an_unscheduled_suite_is_not_quietly_running():
    """The other direction, which is a documentation bug rather than a hole.

    `scheduled=False` is a claim CI does not run this suite — for `manual`,
    that it costs money or needs a person. A workflow selecting it anyway means
    the row is lying to whoever reads `{{CLI}} test --help` before spending
    money.
    """
    exempt = {marker for marker, suite in SUITES.items() if not suite.scheduled}
    running = sorted(exempt & set(selected_markers()))

    assert not running, (
        f"{running} declare `scheduled=False` in cli/test_cmds.py but a workflow selects them: "
        f"{ {m: selected_markers()[m] for m in running} }. Fix the row or the workflow."
    )
