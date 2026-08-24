"""A plan **moves** from the holding tank to the archive, and every index follows.

This is the one flow the docs rules describe as dangerous in both directions:
filing a plan one directory deeper invalidates the relative links inside it and
every link elsewhere that pointed at its old path. `check_doc_links.py` exists
because that had silently produced 141 dead links in the project this shell came
from. Yet the operation itself — `{{CLI}} docs file` — was proven only by
somebody having run it by hand.

The other tests here read the plan tree; this one *changes* it, so it works on a
disposable copy rather than the real repository. That is possible at all because
`scripts/paths.py` derives every path from the location of the package: copy
`cli/` and `scripts/` into a temporary directory and the whole tool operates on
that directory instead, with nothing to patch.

What it pins is the invariant the whole lifecycle rests on: **a plan exists in
exactly one tree at a time.** A copy instead of a move makes "what is left to
do" unanswerable, and every generated index inherits the lie.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

PLAN = """---
title: "Widget Cache"
slug: widget-cache
shelf_status: ready
priority: high
updated: 2024-01-01
tags: []
summary: "Cache widgets so the list endpoint stops recomputing them."
---

# Widget Cache

> **Status**: 🟢 Ready
> **Shelf-Status**: ready
> **Priority**: High — the list endpoint is the slowest route we have

## Tasks

- [x] Measure the current cost
- [x] Add the cache

## Dropped, and why

Nothing yet.
"""


@pytest.fixture
def tree(tmp_path):
    """A disposable project: the real tooling, an empty docs tree."""
    for package in ("cli", "scripts"):
        shutil.copytree(
            PROJECT_ROOT / package,
            tmp_path / package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    for directory in ("docs/TODO", "docs/implementations", "docs/reports/regular"):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "TODO" / "widget-cache.md").write_text(PLAN, encoding="utf-8")
    return tmp_path


def run(tree: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree)
    result = subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=str(tree),
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )
    return result


def index(tree: Path, name: str) -> dict:
    return json.loads((tree / "docs" / name).read_text(encoding="utf-8"))


def test_a_new_plan_reaches_both_generated_artifacts(tree):
    assert run(tree, "docs", "index").returncode == 0

    entries = index(tree, "todo_index.json")["plans"]
    assert [p["slug"] for p in entries] == ["widget-cache"]
    assert "widget-cache" in (tree / "docs" / "TODO" / "README.md").read_text(encoding="utf-8")


def test_queue_order_is_written_and_published(tree):
    """The published order must be the real one — that is why every consumer
    imports `queue_order.py` rather than sorting for itself."""
    assert run(tree, "docs", "index").returncode == 0
    result = run(tree, "docs", "queue-order", "widget-cache", "20")
    assert result.returncode == 0, result.stderr

    assert "> **Queue-Order**: 20" in (tree / "docs" / "TODO" / "widget-cache.md").read_text(encoding="utf-8")
    assert index(tree, "todo_index.json")["plans"][0]["queue_order"] == 20


def test_filing_moves_the_plan_and_never_copies_it(tree):
    """The invariant the whole lifecycle rests on."""
    assert run(tree, "docs", "index").returncode == 0
    result = run(tree, "docs", "file", "widget-cache", "--category", "backend")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    assert not (tree / "docs" / "TODO" / "widget-cache.md").exists(), "the plan is still in the tank"
    assert (tree / "docs" / "implementations" / "backend" / "widget-cache.md").exists()

    assert [p["slug"] for p in index(tree, "todo_index.json")["plans"]] == []
    archived = [d["slug"] for d in index(tree, "implementation_index.json")["implementations"]]
    assert archived == ["widget-cache"]


def test_filing_refuses_a_plan_with_open_tasks(tree):
    """A plan with work left is not finished, whatever the status line says."""
    plan = tree / "docs" / "TODO" / "widget-cache.md"
    plan.write_text(PLAN.replace("- [x] Add the cache", "- [ ] Add the cache"), encoding="utf-8")
    assert run(tree, "docs", "index").returncode == 0

    result = run(tree, "docs", "file", "widget-cache", "--category", "backend")
    assert result.returncode != 0
    assert plan.exists(), "refused, but the plan moved anyway"
    assert not (tree / "docs" / "implementations" / "backend").exists()


def test_the_dry_run_changes_nothing(tree):
    assert run(tree, "docs", "index").returncode == 0
    before = (tree / "docs" / "TODO" / "widget-cache.md").read_text(encoding="utf-8")

    result = run(tree, "docs", "file", "widget-cache", "--category", "backend", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert (tree / "docs" / "TODO" / "widget-cache.md").read_text(encoding="utf-8") == before
    assert not (tree / "docs" / "implementations" / "backend").exists()


def test_the_generators_are_idempotent_after_a_filing(tree):
    """`--check` must be clean straight after a write, or the pre-commit hook
    fails on a tree nobody touched — and a gate people expect red is a gate
    that has stopped working."""
    assert run(tree, "docs", "index").returncode == 0
    assert run(tree, "docs", "file", "widget-cache", "--category", "backend").returncode == 0

    result = run(tree, "docs", "index", "--check")
    assert result.returncode == 0, f"regeneration was owed straight after a filing:\n{result.stdout}"
