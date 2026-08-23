#!/usr/bin/env python3
"""Validate relative markdown links between docs — and their `#fragments`.

Runs as a **ratchet** against `scripts/doc_links_baseline.json`, not a
pass/fail: a project adopting this mid-life has dead links already, and a gate
that is red on arrival gets disabled. The baseline is the count you inherited;
it may only go down.

Why this exists as its own checker: filing a completed plan one directory deeper
invalidates every relative link *inside* it (`../reports/x.md` now needs
`../../`) **and** every link elsewhere that pointed at its old path. In the
project this was extracted from, that had silently produced 141 dead links, 128
of them inside the archive — the filing process was generating the rot at a
steady rate and nothing caught it.

**Repoint, never delete.** A link whose target is genuinely gone gets its
sentence rewritten to name the successor, or de-linked to a backticked path plus
the commit that removed it. These links are prose that records why the docs say
what they say.

Usage:  python scripts/check_doc_links.py [--json] [--update-baseline]

`--json` is additive: the payload goes to stdout, the explanation to stderr.
See `scripts/output.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.output import detail, emit, fail, item, ok  # noqa: E402

BASELINE = REPO_ROOT / "scripts" / "doc_links_baseline.json"
IGNORE_FILE = REPO_ROOT / ".github" / "scripts" / ".validate-ignore"

SCAN_ROOTS = ["docs", ".claude", ".github"]
EXTRA_FILES = ["CLAUDE.md", "README.md"]

_LINK = re.compile(r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<href>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HEADING = re.compile(r"^(#{1,6})\s+(?P<text>.+?)\s*$", re.MULTILINE)
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
#: HTML comments hold examples and scaffolding notes. A link inside one is
#: illustrative, not a reference — checking it makes the template itself red,
#: which teaches that red is normal.
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def slugify(heading: str) -> str:
    """GitHub's heading-anchor algorithm, near enough for our purposes."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", text).strip("-")


def _ignored() -> set:
    if not IGNORE_FILE.exists():
        return set()
    return {
        line.strip()
        for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def markdown_files() -> List[Path]:
    out = []
    for root in SCAN_ROOTS:
        out.extend(sorted((REPO_ROOT / root).rglob("*.md")))
    out.extend(REPO_ROOT / name for name in EXTRA_FILES if (REPO_ROOT / name).exists())
    return [p for p in out if "node_modules" not in p.parts]


def _strip(text: str) -> str:
    return _COMMENT.sub("", _CODE_FENCE.sub("", text))


def headings(path: Path) -> set:
    body = _strip(path.read_text(encoding="utf-8"))
    return {slugify(m.group("text")) for m in _HEADING.finditer(body)}


def _suggest(target: Path) -> str:
    """Where the target probably moved to — same basename, anywhere in docs/."""
    matches = [p for p in (REPO_ROOT / "docs").rglob(target.name)] if (REPO_ROOT / "docs").exists() else []
    return f"  → probably {matches[0].relative_to(REPO_ROOT)}" if len(matches) == 1 else ""


def scan() -> Tuple[List[str], List[str]]:
    ignore = _ignored()
    dead_paths: List[str] = []
    dead_anchors: List[str] = []
    heading_cache: Dict[Path, set] = {}

    for source in markdown_files():
        body = _strip(source.read_text(encoding="utf-8"))
        rel_source = source.relative_to(REPO_ROOT)
        for match in _LINK.finditer(body):
            href = match.group("href")
            if href.startswith(("http://", "https://", "mailto:", "#")):
                # Same-file fragments are checked against this file's headings.
                if href.startswith("#"):
                    anchor = href[1:]
                    if f"{rel_source}{href}" in ignore:
                        continue
                    if anchor and anchor not in heading_cache.setdefault(source, headings(source)):
                        dead_anchors.append(f"{rel_source}: '{href}' matches no heading here")
                continue

            path_part, _, anchor = href.partition("#")
            if not path_part:
                continue
            target = (source.parent / path_part).resolve()
            rel_target = path_part
            if f"{rel_source}#{anchor}" in ignore or path_part in ignore:
                continue
            if not target.exists():
                dead_paths.append(f"{rel_source}: '{rel_target}' does not exist{_suggest(Path(path_part))}")
                continue
            if anchor and target.suffix == ".md":
                if anchor not in heading_cache.setdefault(target, headings(target)):
                    dead_anchors.append(f"{rel_source}: '{href}' — no such heading in {target.relative_to(REPO_ROOT)}")

    return dead_paths, dead_anchors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--update-baseline", action="store_true", help="record the current counts as the new ceiling")
    args = parser.parse_args()

    dead_paths, dead_anchors = scan()
    baseline = (
        json.loads(BASELINE.read_text(encoding="utf-8"))
        if BASELINE.exists()
        else {"max_broken": 0, "max_dead_anchors": 0}
    )

    if args.update_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": "Ratchet ceiling for scripts/check_doc_links.py. These may only go DOWN.",
                    "max_broken": len(dead_paths),
                    "max_dead_anchors": len(dead_anchors),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if args.json:
            emit({"broken": dead_paths, "dead_anchors": dead_anchors, "baseline_updated": True})
        ok(f"baseline set to {len(dead_paths)} broken / {len(dead_anchors)} dead anchors")
        return 0

    if args.json:
        emit({"broken": dead_paths, "dead_anchors": dead_anchors, "baseline": baseline})

    status = 0
    for label, found, ceiling in (
        ("broken links", dead_paths, baseline.get("max_broken", 0)),
        ("dead anchors", dead_anchors, baseline.get("max_dead_anchors", 0)),
    ):
        if len(found) > ceiling:
            fail(f"{len(found)} {label} (ceiling {ceiling}) — repoint them, never delete:")
            for entry in found[:40]:
                item(entry)
            if len(found) > 40:
                detail(f"… and {len(found) - 40} more")
            status = 1
        elif len(found) < ceiling:
            ok(f"{len(found)} {label} — below the {ceiling} ceiling. Lower it in this commit:")
            detail("  python scripts/check_doc_links.py --update-baseline")
        else:
            ok(f"{label}: {len(found)} (at the ceiling)")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
