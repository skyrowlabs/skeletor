"""The draft gate's load-bearing pieces cannot be removed silently.

Two of them look like boilerplate and are not:

* `ready_for_review` in ci.yml's trigger types. Remove it and the gated jobs
  never re-run when a PR flips out of draft — they stay `skipped`, branch
  protection ACCEPTS a skipped required context, and the PR merges having run
  only the gate job.

* The shared docs-only definition. Two copies of that rule drift, and the copy
  that is wrong is the one deciding whether tests run.
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

from scripts.paths import GITHUB_DIR  # noqa: E402

CI = GITHUB_DIR / "workflows" / "ci.yml"
GATE_MODULE = GITHUB_DIR / "scripts" / "docs-only.cjs"


def test_ready_for_review_is_a_trigger():
    assert "ready_for_review" in CI.read_text(encoding="utf-8"), (
        "ci.yml no longer triggers on `ready_for_review`. Gated jobs will never re-run when a PR "
        "leaves draft — they stay `skipped`, which branch protection accepts, and the PR merges "
        "having proven nothing."
    )


def test_gate_definition_is_shared_not_inlined():
    text = CI.read_text(encoding="utf-8")
    assert GATE_MODULE.exists(), "the shared docs-only definition is missing"
    assert "docs-only.cjs" in text, "ci.yml must require the shared definition, never re-inline the pattern"


def test_expensive_jobs_are_gated_on_the_gate_output():
    text = CI.read_text(encoding="utf-8")
    assert "needs.gate.outputs.full_suite" in text, "no job is gated on the gate's verdict — the gate buys nothing"


def test_skipping_is_at_job_level_not_paths_ignore():
    """A required context that never REPORTS blocks a PR forever; one that
    reports `skipped` satisfies branch protection. So gating must be `if:` on
    the job, never `paths-ignore` on the trigger."""
    # The KEY, not the word: this file's own comments explain why paths-ignore
    # is wrong, and a substring check would fail on the explanation.
    text = CI.read_text(encoding="utf-8")
    assert not re.search(r"^\s+paths-ignore:", text, re.MULTILINE), (
        "ci.yml uses `paths-ignore`. A required check skipped by a trigger filter never reports at "
        "all, and a never-reported required context blocks the PR forever. Gate at the job level."
    )
