"""Pin the docs pipeline's invariants — the ones a generator cannot self-check.

Each of these was a real failure in the project this was extracted from, and
each is cheap to re-break: they are properties of *documents*, which are edited
far more often than the code that reads them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.docs import plans  # noqa: E402
from scripts.docs.queue_order import UNORDERED, queue_position, run_order  # noqa: E402


@pytest.fixture(scope="module")
def tank():
    return [p for p in plans.scan(plans.TODO_DIR) if not p.auto_generated]


def test_every_gated_plan_names_its_gate(tank):
    """`blocked`/`shelved`/`deferred` must say what they are waiting for.

    A plan filed under no gate is a plan nobody picks up: the whole point of the
    gate is that plans sharing one clear together in a single sitting.
    """
    unclassified = [p.slug for p in tank if p.shelf_status in plans.GATED and p.blocked_on == "unclassified"]
    assert not unclassified, (
        "Gated plans with no `> **Blocked-On**:` line: "
        + ", ".join(unclassified)
        + f"\nValid gates: {', '.join(plans.GATES)}"
    )


def test_ungated_statuses_carry_no_gate(tank):
    """A gate on a `ready`/`planned`/`in-progress` plan is a contradiction."""
    contradictions = [p.slug for p in tank if p.shelf_status not in plans.GATED and p.blocked_on]
    assert not contradictions, f"Non-gated plans carrying a gate: {contradictions}"


def test_ready_means_an_agent_can_actually_take_it(tank):
    """`ready` is a work queue, not a label.

    Promoting a plan to `ready` *is* the act of handing it to an agent. A plan
    whose remaining work needs a human is `blocked`, however agent-doable the
    rest of it is — an agent that does the agent-half alone leaves the system in
    a state neither half describes.
    """
    offenders = {}
    for plan in tank:
        if plan.shelf_status != "ready":
            continue
        human_tasks = [t for t in plan.open_tasks(include_exempt=True) if "(~operator)" in t]
        if human_tasks:
            offenders[plan.slug] = human_tasks
    assert (
        not offenders
    ), "These plans are `ready` but still carry operator-only tasks — mark them `blocked`:\n" + "\n".join(
        f"  {slug}: {tasks}" for slug, tasks in offenders.items()
    )


def test_queue_order_is_never_inferred_and_never_duplicated(tank):
    """Two plans at one number reintroduces the alphabetical tiebreak the
    numbering exists to remove — and does it invisibly."""
    seen = {}
    for plan in tank:
        if plan.queue_order is None:
            continue
        assert plan.queue_order not in seen, (
            f"queue position {plan.queue_order} claimed by both '{seen[plan.queue_order]}' and '{plan.slug}' "
            f"— use `{{CLI}} docs queue-order <slug> <n>`, which refuses a taken position"
        )
        seen[plan.queue_order] = plan.slug


def test_unnumbered_plans_never_displace_numbered_ones():
    """Absence is not a choice, so it sorts last."""
    numbered = {"slug": "z-numbered", "queue_order": 999, "priority": "low"}
    unnumbered = {"slug": "a-unnumbered", "queue_order": None, "priority": "critical"}
    assert run_order(numbered) < run_order(unnumbered)
    assert queue_position(unnumbered) == UNORDERED


def test_a_malformed_queue_order_sorts_last_rather_than_winning():
    assert queue_position({"queue_order": "soon"}) == UNORDERED
    assert queue_position({"queue_order": []}) == UNORDERED


def test_generated_docs_are_current():
    """The indexes and READMEs must match the plan tree in the commit that
    changed it — a stale generated file lands inside something nobody reviews."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/docs/regen.py", "--check"], cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    assert result.returncode == 0, f"Generated docs are stale — run `{{CLI}} docs index`:\n{result.stdout}"


def test_no_plan_exists_in_both_trees():
    """A plan moves; it never copies. Two copies makes 'what is left to do'
    unanswerable, and the archive copy is the one people read."""
    tank_slugs = {p.slug for p in plans.scan(plans.TODO_DIR)}
    archive_slugs = {p.slug for p in plans.scan(plans.IMPL_DIR, recursive=True)}
    both = tank_slugs & archive_slugs
    assert not both, f"Plans present in BOTH docs/TODO/ and docs/implementations/: {sorted(both)}"
