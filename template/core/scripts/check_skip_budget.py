#!/usr/bin/env python3
"""Fail a suite whose skip count exceeds its budget.

Skips are how a test suite quietly stops testing. A run reporting
"340 passed, 176 skipped" reads as green and proves much less than it appears
to — and nothing surfaces the drift, because each individual skip was
reasonable when it was added.

The budget makes the count a number somebody has to change on purpose.

Usage:
    pytest ... --junitxml=tmp/junit.xml && python scripts/check_skip_budget.py --suite unit
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGET = REPO_ROOT / "tests" / "skip_budget.json"
DEFAULT_JUNIT = REPO_ROOT / "tmp" / "junit.xml"


def count_skips(junit: Path) -> tuple:
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    total = sum(int(s.get("tests", 0)) for s in suites)
    reasons = [
        (case.get("classname", ""), skip.get("message", ""))
        for suite in suites
        for case in suite.iter("testcase")
        for skip in case.iter("skipped")
    ]
    return skipped, total, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="unit")
    parser.add_argument("--junit", type=Path, default=DEFAULT_JUNIT)
    parser.add_argument("--update", action="store_true", help="record the observed count as the new ceiling")
    args = parser.parse_args()

    if not args.junit.exists():
        print(f"⚠️  no junit report at {args.junit} — run pytest with --junitxml first")
        return 0

    budget = json.loads(BUDGET.read_text(encoding="utf-8"))
    ceiling = budget["suites"].get(args.suite, {}).get("max_skipped")
    if ceiling is None:
        print(f"❌ suite '{args.suite}' has no entry in tests/skip_budget.json — add one")
        return 1

    skipped, total, reasons = count_skips(args.junit)

    if args.update:
        budget["suites"][args.suite]["max_skipped"] = skipped
        BUDGET.write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
        print(f"✅ {args.suite} budget set to {skipped}")
        return 0

    if skipped > ceiling:
        print(f"❌ {args.suite}: {skipped} skipped, budget {ceiling} ({total} tests)")
        for classname, message in reasons[:20]:
            print(f"   · {classname}: {message[:100]}")
        print("\n   Fix the skip, or raise the budget IN THIS COMMIT and justify it in the body.")
        return 1

    if skipped < ceiling:
        print(f"✅ {args.suite}: {skipped} skipped, under the {ceiling} budget.")
        print(f"   Lower it in this commit: python scripts/check_skip_budget.py --suite {args.suite} --update")
        return 0

    print(f"✅ {args.suite}: {skipped} skipped (at budget)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
