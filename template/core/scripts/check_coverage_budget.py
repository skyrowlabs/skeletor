"""Fail a suite whose coverage drops below its baseline, within a tolerance.

A ratchet, not a target. The distinction matters: a test written to move a
percentage covers the lines that were cheapest to reach, which are the lines
least likely to be wrong. The number exists to stop coverage sliding while
nobody is looking — not to be optimised.

The tolerance absorbs honest run-to-run variance (an env-gated branch, a
skipped optional dependency) without absorbing a real regression.

Usage:
    pytest --cov --cov-report=xml:tmp/coverage.xml && python scripts/check_coverage_budget.py --suite unit
    python scripts/check_coverage_budget.py --suite unit --json

`--json` reports on **every** path, including the ones that pass. A ratchet a
dashboard can only read when it is red tells you nothing about the direction it
has been moving, which is the only thing a ratchet is for.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import detail, emit, fail, ok, warn  # noqa: E402
from scripts.paths import TESTS_DIR, TMP_DIR  # noqa: E402

BUDGET = TESTS_DIR / "coverage_budget.json"
DEFAULT_XML = TMP_DIR / "coverage.xml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="unit")
    parser.add_argument("--xml", type=Path, default=DEFAULT_XML)
    parser.add_argument("--update", action="store_true", help="record the observed percentage as the new baseline")
    parser.add_argument("--json", action="store_true", help="emit the result on stdout as well")
    args = parser.parse_args()

    def done(payload: dict, status: int) -> int:
        """One exit, one payload. Emitting per-branch is how a path loses its."""
        if args.json:
            emit({"suite": args.suite, **payload})
        return status

    if not args.xml.exists():
        warn(f"no coverage report at {args.xml} — run pytest with --cov-report=xml first")
        return done({"state": "no-report", "xml": str(args.xml)}, 0)

    budget = json.loads(BUDGET.read_text(encoding="utf-8"))
    entry = budget["suites"].get(args.suite)
    if entry is None:
        fail(f"suite '{args.suite}' has no entry in tests/coverage_budget.json — add one")
        return done({"state": "unbudgeted"}, 1)

    observed = float(ET.parse(args.xml).getroot().get("line-rate", 0)) * 100
    baseline = float(entry["baseline_pct"])
    tolerance = float(budget.get("tolerance_pts", 0.5))
    measured = {"observed_pct": round(observed, 2), "baseline_pct": baseline, "tolerance_pts": tolerance}

    if args.update:
        entry["baseline_pct"] = round(observed, 2)
        BUDGET.write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
        ok(f"{args.suite} baseline set to {observed:.2f}%")
        return done({"state": "updated", **measured}, 0)

    if observed < baseline - tolerance:
        fail(f"{args.suite}: {observed:.2f}% vs baseline {baseline:.2f}% (tolerance {tolerance})")
        detail("Cover what you changed, or say in the commit body why the drop is correct.")
        return done({"state": "below", **measured}, 1)

    if observed > baseline + tolerance:
        ok(f"{args.suite}: {observed:.2f}% — above baseline {baseline:.2f}%.")
        detail(f"Lock it in: python scripts/check_coverage_budget.py --suite {args.suite} --update")
        return done({"state": "above", **measured}, 0)

    ok(f"{args.suite}: {observed:.2f}% (baseline {baseline:.2f}%)")
    return done({"state": "within", **measured}, 0)


if __name__ == "__main__":
    raise SystemExit(main())
