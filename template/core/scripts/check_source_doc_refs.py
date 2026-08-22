#!/usr/bin/env python3
"""Validate `docs/**` paths cited from **source comments** — the other direction.

Doc-to-code references get checked by every "does this file exist" linter.
Code-to-doc references — the `# see docs/TODO/x.md` comments that record why a
gate is free, why a check is fail-closed, why a column was dropped — are checked
by nothing, and they break every time a completed plan is filed to the archive.
In the project this was extracted from, 85% of ~450 such references were dead by
the time anyone measured.

**Repoint, never delete.** Deleting the reference to silence the check destroys
the only record of why the code is shaped that way.

Paths that name nothing real by design — help text, output destinations, test
fixtures — go in `.github/scripts/.validate-ignore`.

Usage:  python scripts/check_source_doc_refs.py [--json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORE_FILE = REPO_ROOT / ".github" / "scripts" / ".validate-ignore"

SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".sh", ".yml", ".yaml", ".toml"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", "tmp", ".claude/worktrees"}

_REF = re.compile(r"(?P<path>docs/[A-Za-z0-9_./-]+\.(?:md|json|ya?ml))")


def _ignored() -> set:
    if not IGNORE_FILE.exists():
        return set()
    return {
        line.strip()
        for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _sources() -> List[Path]:
    out = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def _successor(name: str) -> str:
    """Filing moves a plan; the successor is the same basename elsewhere."""
    matches = list((REPO_ROOT / "docs").rglob(Path(name).name))
    return f"  → now at {matches[0].relative_to(REPO_ROOT)}" if len(matches) == 1 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ignore = _ignored()
    dead: List[str] = []
    checked = 0

    for source in _sources():
        try:
            text = source.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in _REF.finditer(line):
                ref = match.group("path")
                if ref in ignore:
                    continue
                checked += 1
                if not (REPO_ROOT / ref).exists():
                    dead.append(f"{source.relative_to(REPO_ROOT)}:{lineno}: {ref}{_successor(ref)}")

    if args.json:
        print(json.dumps({"checked": checked, "dead": dead}, indent=2))
        return 1 if dead else 0

    if dead:
        print(f"❌ {len(dead)} dead doc reference(s) in source — repoint them, never delete:")
        for line in dead:
            print(f"   · {line}")
        print("\n   A reference that names nothing by design goes in .github/scripts/.validate-ignore")
        return 1
    print(f"✅ {checked} doc reference(s) in source, all resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
