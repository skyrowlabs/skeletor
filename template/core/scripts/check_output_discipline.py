#!/usr/bin/env python3
"""Nobody spells a status symbol, or picks a stream, outside `scripts/output.py`.

The rule this enforces is in `.claude/rules/output.md`, and it exists because it
was already broken here. `cli/helpers.py` shipped `ok()` / `fail()` / `warn()`
and roughly twenty call sites retyped `print(f"✅ ...")` anyway; `⏸️` meant
"executed and declined" in three files and was defined in none of them; the gate
table had a second implementation in `cli/commit.py`; and four scripts grew a
`--json` flag while writing their human output to the same stdout, so three of
them emitted something no parser could read.

Every one of those is invisible to a linter and to review, because each file is
internally consistent. That is the same shape as the workflow-drift bug, and it
gets the same treatment: enrol by pattern, exempt with a written reason.

**Enrolment is not a registry.** Every `.py` under `cli/` and `scripts/` is
checked. Exemptions live in `scripts/output_allowlist.yaml` WITH A REASON — an
intended divergence is a decision record; an unintended one is a failure.

Usage:  python scripts/check_output_discipline.py [--json]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.output import STATE_SYMBOLS, detail, emit, fail, item, ok  # noqa: E402

ALLOWLIST = REPO_ROOT / "scripts" / "output_allowlist.yaml"

#: Where emissions are allowed to originate. `scripts/output.py` owns the
#: streams; it is the one file that must write to them directly.
SCAN_DIRS = ["cli", "scripts"]
OWNER = "scripts/output.py"

#: Anything that puts characters in front of a person or a pipe.
_EMIT = re.compile(r"\b(?:print|(?:click\.)?echo|secho)\s*\(|\braise SystemExit\s*\(\s*[\"'f]")

#: Choosing a stream by hand is the other half of the same mistake: it is how a
#: `--json` payload ends up interleaved with the ❌ lines explaining it.
_STREAM = re.compile(r"file\s*=\s*sys\.(?:stdout|stderr)|sys\.(?:stdout|stderr)\.write\s*\(")

#: The state symbols only, read from the module that owns them. A `→` inside
#: generated prose is punctuation, and a ✅ inside a generated markdown table is
#: content — flagging either would make the docs generators unfixable.
_GLYPHS = tuple(sorted({symbol.strip() for symbol in STATE_SYMBOLS.values()}))


def _allowlist() -> Dict[str, str]:
    """Minimal reader for the flat `path: reason` shape this file uses.

    A YAML parser would be more correct and would add a dependency to a check
    that must run on any host, including one with nothing installed yet.
    """
    if not ALLOWLIST.exists():
        return {}
    out: Dict[str, str] = {}
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, reason = stripped.partition(":")
        out[key.strip()] = reason.strip().strip("\"'")
    return out


def _prose_lines(text: str) -> set:
    """Line numbers inside a docstring — writing *about* output is not output.

    Without this the checker fails on its own docstring, and on every module
    that documents the rule it enforces. A docstring is exactly a bare string
    expression, so `ast` answers this precisely; a regex would not.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    lines: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return lines


def _sources() -> List[Path]:
    found: List[Path] = []
    for directory in SCAN_DIRS:
        root = REPO_ROOT / directory
        if root.exists():
            found.extend(sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts))
    return found


def scan() -> Dict[str, List[str]]:
    """Every place a symbol is spelled, a stream is picked, or `--json` is absent."""
    allowlist = _allowlist()
    spelled: List[str] = []
    streams: List[str] = []
    unflagged: List[str] = []

    for path in _sources():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == OWNER or rel in allowlist:
            continue
        text = path.read_text(encoding="utf-8")
        prose = _prose_lines(text)

        for lineno, source_line in enumerate(text.splitlines(), 1):
            if lineno in prose or source_line.lstrip().startswith("#"):
                continue
            if _EMIT.search(source_line) and any(glyph in source_line for glyph in _GLYPHS):
                spelled.append(f"{rel}:{lineno}: status symbol inside an emission — use scripts/output.py")
            if _STREAM.search(source_line):
                streams.append(f"{rel}:{lineno}: picks a stream by hand — use `line`/`emit` or a status helper")

        # A gate a dashboard cannot read is a gate nobody watches over time.
        if path.name.startswith("check_") and 'add_argument("--json"' not in text:
            unflagged.append(f"{rel}: a check script with no --json")

    return {"spelled": spelled, "streams": streams, "unflagged": unflagged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = scan()
    checked = len(_sources())
    exempt = _allowlist()

    if args.json:
        emit({"checked": checked, "exempt": sorted(exempt), **findings})

    total = sum(len(v) for v in findings.values())
    if total:
        fail(f"{total} output-discipline finding(s) across {checked} file(s):")
        for group in ("spelled", "streams", "unflagged"):
            for finding in findings[group]:
                item(finding)
        detail()
        detail("Status lines come from scripts/output.py — see .claude/rules/output.md.")
        detail("A deliberate exception goes in scripts/output_allowlist.yaml WITH A REASON.")
        return 1

    ok(f"{checked} file(s) route output through scripts/output.py ({len(exempt)} exempt by allowlist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
