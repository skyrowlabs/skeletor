"""Every test file declares which environment runs it.

This is what makes marker-based registration work: a file joins a suite by
declaring a marker, and nothing else needs updating — no CI step, no runner
case, no CLI entry. The guarantee only holds if *every* file declares one, so an
undeclared file fails the unit suite rather than silently never running.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

TESTS_DIR = Path(__file__).resolve().parent
KNOWN_MARKERS = {"unit", "integration", "manual", "slow", "security"}

_PYTESTMARK = re.compile(r"^pytestmark\s*=\s*(?P<value>.+)$", re.MULTILINE)
_MARKER = re.compile(r"pytest\.mark\.(?P<name>\w+)")


def _test_files():
    return sorted(p for p in TESTS_DIR.rglob("test_*.py") if "__pycache__" not in p.parts)


def test_the_scan_found_the_test_files():
    """A marker check over zero files is green and worth nothing.

    The `filesAnalyzed` lesson, which this repository states for pyright and for
    its lint gates and had not applied to its own suites: nothing in a pass
    distinguishes *every file declares a marker* from *no file was looked at*.
    Rename or move `tests/`, and the enumeration returns nothing while every
    assertion below keeps passing — the check disarms itself silently, which is
    the failure marker-based suites exist to prevent, arriving in the gate that
    enforces them.

    Confirmed by forcing the enumeration empty: this file passed 2/2 before this
    test existed. Reported as a class by proto.pilot — a negative assertion is
    where a mis-aimed check goes quiet, because a green negative looks identical
    whether the thing did not happen or nobody looked.
    """
    assert _test_files(), f"no test_*.py found under {TESTS_DIR} — the scan matched nothing"


def test_every_test_file_declares_a_suite_marker():
    undeclared = []
    for path in _test_files():
        source = path.read_text(encoding="utf-8")
        match = _PYTESTMARK.search(source)
        if not match:
            undeclared.append(str(path.relative_to(TESTS_DIR)))
            continue
        if not _MARKER.findall(match.group("value")):
            undeclared.append(str(path.relative_to(TESTS_DIR)))

    assert not undeclared, (
        "These test files declare no module-wide pytestmark, so no suite runs them:\n  "
        + "\n  ".join(undeclared)
        + "\n\nAdd one at module level, e.g.  pytestmark = [pytest.mark.unit]"
    )


def test_declared_markers_are_registered():
    """A typo'd marker silently matches nothing — --strict-markers only catches
    markers pytest is *asked* about, not ones a file assigns itself."""
    unknown = {}
    for path in _test_files():
        match = _PYTESTMARK.search(path.read_text(encoding="utf-8"))
        if not match:
            continue
        names = set(_MARKER.findall(match.group("value"))) - KNOWN_MARKERS
        if names:
            unknown[str(path.relative_to(TESTS_DIR))] = sorted(names)

    assert not unknown, f"Unregistered markers (add them to tests/pytest.ini): {unknown}"
