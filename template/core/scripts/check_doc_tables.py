#!/usr/bin/env python3
"""Every `docs/*.md` is registered in both agent-facing index tables.

`CLAUDE.md` and `.github/DOCS_INDEX.md` are how an agent decides what to read.
A document in neither is a document that will not be loaded — which is the same,
from the agent's point of view, as a document that does not exist. The failure
is silent and permanent: nothing ever surfaces the omission.

The reverse direction matters as much. A table row pointing at a deleted file
sends a reader to a dead path and, worse, implies the subject is still covered.

Usage:  python scripts/check_doc_tables.py [--json]

`--json` is additive, never a second code path: the payload goes to stdout and
the explanation to stderr, so `... --json | jq` and a human run are the same run.
See `scripts/output.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Set

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.output import detail, emit, fail, item, ok  # noqa: E402

DOCS_DIR = REPO_ROOT / "docs"
TABLES = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / ".github" / "DOCS_INDEX.md"]

#: Docs that are indexes themselves, or generated. Registering an index in an
#: index is noise, and a generated file's registration would be regenerated away.
EXEMPT = {"README.md"}

_DOC_PATH = re.compile(r"docs/[A-Za-z0-9_-]+\.md")


def referenced() -> Set[str]:
    seen: Set[str] = set()
    for table in TABLES:
        if table.exists():
            seen |= set(_DOC_PATH.findall(table.read_text(encoding="utf-8")))
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    on_disk = {f"docs/{p.name}" for p in DOCS_DIR.glob("*.md") if p.name not in EXEMPT}
    listed = referenced()

    unregistered = sorted(on_disk - listed)
    dangling = sorted(ref for ref in listed - on_disk if not (REPO_ROOT / ref).exists())

    if args.json:
        emit({"registered": len(on_disk), "unregistered": unregistered, "dangling": dangling})

    status = 0
    if unregistered:
        fail("docs not registered in CLAUDE.md or .github/DOCS_INDEX.md:")
        for ref in unregistered:
            item(ref)
        detail("An unregistered doc is one no agent will load. Add it to both tables.")
        status = 1
    if dangling:
        fail("index rows pointing at files that no longer exist:")
        for ref in dangling:
            item(ref)
        status = 1
    if not status:
        ok(f"{len(on_disk)} doc(s), all registered in both index tables")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
