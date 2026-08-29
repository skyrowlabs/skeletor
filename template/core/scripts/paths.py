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

import os
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

#: Scratch, and gitignored. Tree locks, coverage XML, merge markers — everything
#: whose lifetime is a run rather than a commit, and which nothing will want
#: next week. The record of what ran is **not** here; see `state_dir` below.
TMP_DIR = PROJECT_ROOT / "tmp"


# ── State: the record, outside the checkout ──────────────────────────────────
#: The workspace-wide root for the agentic record — transcripts, ledgers,
#: per-job memory, the payloads agent stages read. Deliberately **not** under
#: `PROJECT_ROOT`, and that is the whole point: it outlives any one checkout, is
#: shared by every worktree of this repo, and cannot be reached by
#: `git clean -fdx`. See `~/skyrow.labs/sl-agent-logs/README.md`.
STATE_ROOT_ENV = "SL_AGENT_LOGS"
STATE_ROOT_DEFAULT = Path.home() / "skyrow.labs" / "sl-agent-logs"

#: This project's directory under that root. Written in rather than taken from
#: `PROJECT_ROOT.name`, because a **linked worktree's directory is not the
#: slug**: a job running in a pool tree would otherwise resolve to a private
#: state root of its own, which is precisely the per-tree scattering this
#: layout exists to end. The slug is a fact about the project, not about which
#: copy of it you happen to be standing in.
STATE_SLUG = "{{PROJECT_SLUG}}"

#: The classes the state root is divided into, named so a caller asks for one
#: rather than spelling a directory — and so a retention sweep has a single list
#: to walk instead of a pattern to guess. Retention differs per class, which is
#: the reason they are directories at all.
LOG = "log"  # the transcript: what every run printed
LEDGER = "ledger"  # append-only structured record, trimmed on write
INPUT = "input"  # the payload an agent stage actually read
MEMORY = "memory"  # what a job saw last time; overwritten every run
INFLIGHT = "inflight"  # what is running right now; removed in a `finally`
PRODUCT = "product"  # a job's own output, overwritten every run


def state_dir(*parts: str) -> Path:
    """This project's state root, plus any path below it.

    A function rather than a constant, unlike everything above, and for one
    reason: a constant freezes the override at import time, so a test that sets
    the environment variable in a fixture gets the live path anyway. The knob
    has to be read when the path is used or it is not a knob.

    **A function here does not save a caller that freezes it.** A module opening
    with ``LEDGER = state_dir(LEDGER, "ledger.jsonl")`` has evaluated this at
    import, and a fixture's ``monkeypatch.setenv`` runs long after that — so the
    suite writes to the live record and every test still passes. Resolve at the
    point of use, or set the variable at ``conftest.py`` import time. It is
    invisible by construction: ``test_state_paths.py`` excludes shared
    append-only files, correctly, which also means it cannot catch a test
    appending to them.

    **One resolver for readers and the writer alike.** Split them — define the
    write path here and the read path in the module that consumes it — and a
    test can point the write at a scratch file while the read still finds the
    live one. It passes, and proves nothing. That is not hypothetical: it is
    why this function exists instead of the three definitions it replaced.
    """
    root = os.environ.get(STATE_ROOT_ENV) or STATE_ROOT_DEFAULT
    return Path(root, STATE_SLUG, *parts)
