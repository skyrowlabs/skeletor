#!/usr/bin/env python3
"""Every `docs/*.md` is registered in both agent-facing index tables.

`CLAUDE.md` and `.github/DOCS_INDEX.md` are how an agent decides what to read.
A document in neither is a document that will not be loaded — which is the same,
from the agent's point of view, as a document that does not exist. The failure
is silent and permanent: nothing ever surfaces the omission.

The reverse direction matters as much. A table row pointing at a deleted file
sends a reader to a dead path and, worse, implies the subject is still covered.

Usage:  python scripts/check_doc_tables.py [--json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Set

REPO_ROOT = Path(__file__).resolve().parents[1]
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
        print(json.dumps({"unregistered": unregistered, "dangling": dangling}, indent=2))

    status = 0
    if unregistered:
        print("❌ docs not registered in CLAUDE.md or .github/DOCS_INDEX.md:")
        for ref in unregistered:
            print(f"   · {ref}")
        print("   An unregistered doc is one no agent will load. Add it to both tables.")
        status = 1
    if dangling:
        print("❌ index rows pointing at files that no longer exist:")
        for ref in dangling:
            print(f"   · {ref}")
        status = 1
    if not status:
        print(f"✅ {len(on_disk)} doc(s), all registered in both index tables")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
