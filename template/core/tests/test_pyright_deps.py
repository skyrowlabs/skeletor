"""What pyright imports in CI is declared in one file, and it is a superset.

`reportMissingImports` is `none`, so a package pyright cannot import becomes
`Unknown` and stops constraining anything downstream. A type-check job with a
leaner environment than the test job therefore does not fail — it checks *less*,
silently, and the errors it does report land in files the commit never touched.

`.github/pyright-deps.txt` is where that set is declared, and two things have to
hold for the declaration to mean anything. Neither is visible from the file:

* the type-check job must **install from it** rather than inlining its own list,
  because a second list is a second thing to remember; and
* it must **reach** every requirements file the test jobs install, because
  "superset" is the whole claim and a `-r` chain is how it is expressed.

Both are asserted by walking the workflows. The test side is **sized**, because
a set that stopped matching would pass the superset rule while looking at
nothing. The pyright side is **partitioned** instead: zero type-check jobs is a
real configuration, not a broken scan, and sizing it says the wrong one of those
in a tree whose CI does not type-check. See the first test.

## Enrolment is by pattern, at both ends

A type-check step is any step that runs `pyright`; a test job is any job that
runs `pytest`. Neither is listed, so a second workflow that type-checks, or a
fourth marker job, is enrolled by existing. The requirement set is likewise read
out of the files rather than named here.

## Why the workflows are read with comments blanked

Because this hunts for a *requirement*, and the string most likely to appear in a
job that has **not** done the thing is a comment saying it should — the shape
`scripts/yaml_text.py` was written for. A `# we should install pyright-deps here`
satisfies a substring check perfectly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which owns
# every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scanning import scanned  # noqa: E402
from scripts.paths import GITHUB_DIR, PROJECT_ROOT  # noqa: E402
from tests.workflows import jobs  # noqa: E402

WORKFLOWS = GITHUB_DIR / "workflows"
DEPS = GITHUB_DIR / "pyright-deps.txt"

#: `pip install -r <file>`, however the line is spelled around it.
_REQUIREMENT = re.compile(r"pip\s+install\s+(?:-\S+\s+)*-r\s+(?P<path>[\w./\-]+)")

#: A requirement file including another one. pip resolves the path relative to
#: the including file's directory, which is why this returns the raw string and
#: the caller does the joining.
_INCLUDE = re.compile(r"^\s*-r\s+(?P<path>\S+)", re.MULTILINE)


def _type_check_jobs() -> dict:
    """`{(workflow, job): body}` for every job that runs pyright."""
    found = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job, body in jobs(path).items():
            if re.search(r"\bpyright\b", body):
                found[(path.name, job)] = body
    return found


def _test_jobs() -> dict:
    """`{(workflow, job): body}` for every job that runs pytest."""
    found = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job, body in jobs(path).items():
            if "pytest" in body:
                found[(path.name, job)] = body
    return found


def _requirements(body: str) -> set:
    """Every requirements file a job installs with `-r`, repo-relative.

    A leading `./` is dropped and nothing else is: `lstrip("./")` reads as that
    and is a character set, so it ate the dot off `.github/pyright-deps.txt` and
    reported the one job that is already correct.
    """
    found = set()
    for match in _REQUIREMENT.finditer(body):
        path = match.group("path")
        found.add(path[2:] if path.startswith("./") else path)
    return found


def _reachable(start: Path, seen: set | None = None) -> set:
    """`start` and everything it pulls in through `-r`, repo-relative and resolved."""
    seen = set() if seen is None else seen
    key = start.resolve().relative_to(PROJECT_ROOT).as_posix()
    if key in seen or not start.is_file():
        return seen
    seen.add(key)
    for match in _INCLUDE.finditer(start.read_text(encoding="utf-8")):
        _reachable(start.parent / match.group("path"), seen)
    return seen


def test_the_declaration_and_the_jobs_are_the_same_decision():
    """Declaring a type-check environment and running one are one choice, not two.

    **The two failing corners of a 2x2, and the other two are configurations.**
    This test used to refuse at `least=1` type-check job, which reads *the scan
    broke* — and for a tree whose CI does not type-check, that is not what
    happened. Nothing in the file separated the two, they have opposite
    remedies, and the only escape from the wrong one was deleting the file,
    which takes the superset rule with it. sky.boss reported it having done
    exactly that, with a **true** finding of the superset rule underneath.

    So the discriminator is the declaration, which is a fact the tree states
    rather than one this scan infers:

    * declared, and jobs run it — everything below applies.
    * declared, no job runs it — a dead declaration. Fails, and *delete this
      file* is one of the two remedies named.
    * not declared, no job runs it — this tree does not type-check in CI. Every
      rule below is vacuous, and the assertion here is what keeps that from
      being a silent pass: no job may run pyright.
    * not declared, and a job runs it — the expensive one. A job type-checks
      against an environment nothing writes down, so it checks *less* than the
      tests do and reports a clean run for the gap.

    An empty declaration is the degenerate first corner: a superset of nothing,
    passing silently.
    """
    jobs_ = _type_check_jobs()
    named = ", ".join(f"{workflow}:{job}" for workflow, job in sorted(jobs_))
    if not DEPS.is_file():
        assert not jobs_, (
            f"{named} runs pyright and {DEPS.name} does not exist. Nothing declares what "
            f"that job imports, so it type-checks a leaner environment than the tests do "
            f"— which under `reportMissingImports: none` is a quieter run, not a failing "
            f"one. Restore the file, or stop running pyright in CI."
        )
        return
    assert jobs_, (
        f"{DEPS.name} declares the environment pyright sees in CI and no job here runs "
        f"pyright. Either the job was lost — the rules in this file have been enforcing "
        f"nothing since — or this tree stopped type-checking in CI, in which case delete "
        f"{DEPS.name} and this file goes quiet without taking the superset rule with it."
    )
    scanned(_INCLUDE.findall(DEPS.read_text(encoding="utf-8")), f"requirement includes in {DEPS.name}")


def test_the_scan_finds_the_test_jobs():
    """The test side going empty passes the superset rule while looking at nothing.

    `least=2` is the fixture rule: with one, *every test job* and *this test
    job* are the same set, so a filter over them is unobservable.
    """
    scanned(_test_jobs(), "workflow jobs running pytest", least=2)


def test_a_type_check_job_installs_from_the_declared_set():
    """The set is installed from the file, not inlined beside it."""
    declared = DEPS.relative_to(PROJECT_ROOT).as_posix()
    for (workflow, job), body in _type_check_jobs().items():
        assert declared in _requirements(body), (
            f"{workflow}: job '{job}' runs pyright but never installs `-r {declared}`. "
            f"Whatever it installs instead is a second declaration of the type-check "
            f"environment, and nothing compares the two — so the job checks a different "
            f"tree than the one {declared} describes, and reports no error for the gap."
        )


def test_the_declared_set_reaches_every_test_job_requirement():
    """Superset, expressed the only way a requirements file can express it.

    A package the tests import and pyright cannot is not an error under
    `reportMissingImports: none`. It is `Unknown`, and it stops constraining
    everything it touches — so the shortfall shows up as *fewer* errors, which is
    the direction nobody investigates.
    """
    if not DEPS.is_file():
        # The corner above rules this tree out of the question: nothing is
        # declared, and no job runs pyright, so there is no superset to claim.
        # A `return` rather than a skip — `skip_budget.json` ships at 0, and a
        # suite that goes quiet by emitting skips is a ratchet failure wearing
        # a configuration's clothes.
        return
    declared = _reachable(DEPS)
    missing = {}
    for (workflow, job), body in _test_jobs().items():
        for requirement in sorted(_requirements(body)):
            if requirement not in declared:
                missing.setdefault(requirement, []).append(f"{workflow}:{job}")

    assert not missing, (
        f"{DEPS.name} does not reach every requirements file the test jobs install:\n  "
        + "\n  ".join(f"{req} — installed by {', '.join(jobs_)}" for req, jobs_ in sorted(missing.items()))
        + f"\n\nAdd `-r <relative path>` to {DEPS.name} (paths there resolve from "
        f"{DEPS.parent.name}/). pyright will otherwise see a leaner environment than the "
        "tests do, which reads as a clean run rather than as a check that gave up."
    )
