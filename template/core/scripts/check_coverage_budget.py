"""Fail a suite whose coverage drops below its baseline, within a tolerance.

A ratchet, not a target. The distinction matters: a test written to move a
percentage covers the lines that were cheapest to reach, which are the lines
least likely to be wrong. The number exists to stop coverage sliding while
nobody is looking — not to be optimised.

The tolerance absorbs honest run-to-run variance (an env-gated branch, a
skipped optional dependency) without absorbing a real regression.

Usage:
    pytest --cov --cov-report=xml:tmp/coverage.xml && python scripts/check_coverage_budget.py --suite unit
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGET = REPO_ROOT / "tests" / "coverage_budget.json"
DEFAULT_XML = REPO_ROOT / "tmp" / "coverage.xml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="unit")
    parser.add_argument("--xml", type=Path, default=DEFAULT_XML)
    parser.add_argument("--update", action="store_true", help="record the observed percentage as the new baseline")
    args = parser.parse_args()

    if not args.xml.exists():
        print(f"⚠️  no coverage report at {args.xml} — run pytest with --cov-report=xml first")
        return 0

    budget = json.loads(BUDGET.read_text(encoding="utf-8"))
    entry = budget["suites"].get(args.suite)
    if entry is None:
        print(f"❌ suite '{args.suite}' has no entry in tests/coverage_budget.json — add one")
        return 1

    observed = float(ET.parse(args.xml).getroot().get("line-rate", 0)) * 100
    baseline = float(entry["baseline_pct"])
    tolerance = float(budget.get("tolerance_pts", 0.5))

    if args.update:
        entry["baseline_pct"] = round(observed, 2)
        BUDGET.write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
        print(f"✅ {args.suite} baseline set to {observed:.2f}%")
        return 0

    if observed < baseline - tolerance:
        print(f"❌ {args.suite}: {observed:.2f}% vs baseline {baseline:.2f}% (tolerance {tolerance})")
        print("   Cover what you changed, or say in the commit body why the drop is correct.")
        return 1

    if observed > baseline + tolerance:
        print(f"✅ {args.suite}: {observed:.2f}% — above baseline {baseline:.2f}%.")
        print(f"   Lock it in: python scripts/check_coverage_budget.py --suite {args.suite} --update")
        return 0

    print(f"✅ {args.suite}: {observed:.2f}% (baseline {baseline:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
