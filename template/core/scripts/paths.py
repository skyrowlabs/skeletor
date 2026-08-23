#!/usr/bin/env python3
"""Where this project is on disk — derived once, imported everywhere.

This module exists because the root was being recomputed in **25 places**, each
as `Path(__file__).resolve().parents[N]` with `N` chosen from how deep the file
happened to sit. That is Rule 1 with the serial numbers filed off: a value with
no owner, re-derived by every consumer.

The failure it removes is quiet, which is why it was worth removing. Move
`check_doc_links.py` into a subdirectory and its `parents[1]` still resolves —
to `scripts/`, not the repo. Nothing raises. The checker simply scans a `docs/`
that does not exist, finds nothing, and reports green. Every derived directory
below has been wrong the same way at least once in some codebase.

After this, a file in the wrong place fails at **import**, because the
bootstrap that puts the package on `sys.path` is the thing that breaks — and an
`ImportError` names the file, where a silently-empty scan names nothing.

## The one derivation

`PROJECT_ROOT` is `parents[1]` **of this file specifically**, which is exact and
stays exact: this module is `<root>/scripts/paths.py` by definition, because
that is the path every consumer imports it by.

## The `sys.path` line in each consumer is not a second derivation

A script run by path (`python scripts/check_doc_links.py`) gets `scripts/` on
`sys.path`, not the repo, so it cannot import this module until something puts
the repo there. That bootstrap line is unavoidable and depth-dependent. It is
also *only* about imports: get it wrong and nothing resolves at all, which is
the loud failure this module is trading up to.

## Governing a tree other than this one

Everything below is derived from a single name, so pointing this shell at a
different checkout is one function. It is deliberately **not** built yet,
because it needs an answer this module cannot give on its own: `PROJECT_ROOT`
is currently both "where the code is" and "where the content is", and only the
second should move. Splitting them is a decision about every consumer below,
not a config value — see `docs/DEVELOPMENT.md`. This is where it would land.

Stdlib only, and imported by `cli/` and `scripts/` alike.
"""

from __future__ import annotations

from pathlib import Path

#: The repository root. The only place in the tree this is worked out.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Content ──────────────────────────────────────────────────────────────────
DOCS_DIR = PROJECT_ROOT / "docs"

#: The holding tank and the archive — the two halves of the docs lifecycle. A
#: plan **moves** between them, so both are resolved here rather than by each
#: of the six modules that walk them.
TODO_DIR = DOCS_DIR / "TODO"
IMPL_DIR = DOCS_DIR / "implementations"

#: In-flight reports and their frozen per-release editions.
REGULAR_DIR = DOCS_DIR / "reports" / "regular"
RELEASES_DIR = DOCS_DIR / "reports" / "releases"

# ── Code and configuration ───────────────────────────────────────────────────
CLI_DIR = PROJECT_ROOT / "cli"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
GITHUB_DIR = PROJECT_ROOT / ".github"

#: Scratch, and gitignored. Ledgers, tree locks, coverage XML, merge markers —
#: everything whose lifetime is a run rather than a commit.
TMP_DIR = PROJECT_ROOT / "tmp"
