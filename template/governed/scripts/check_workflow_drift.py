#!/usr/bin/env python3
"""Every job that stands up the stack does it the same way.

The bug this exists for: two workflows both booted the stack, one of them was
missing a setup step the other had, and three tests failed **every** run for two
days while the same tests passed in the other workflow. Nobody looked, because
each job's history was internally consistent.

Two design choices are load-bearing:

**Enrolment is automatic, not a registry.** Any job matching the enrolment
pattern is checked. A registry of "jobs that stand up the stack" would need
updating by whoever adds the next one — and forgetting to update a registry is
exactly the same class of bug this check exists to catch.

**Exemptions are written down with a reason.** A divergence that is intended is
fine; a divergence nobody decided is the failure. The allowlist entry is the
decision record.

Usage:  python scripts/check_workflow_drift.py [--json]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.output import detail, emit, fail, item, ok  # noqa: E402

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
ALLOWLIST = REPO_ROOT / "scripts" / "workflow_drift_allowlist.yaml"

#: A job is enrolled if its text matches ANY of these — i.e. if it stands the
#: stack up at all, however it does it.
ENROLMENT_PATTERNS = [
    re.compile(r"docker\s+compose\s+up"),
    re.compile(r"uses:\s*\./\.github/actions/\S*stack"),
]

#: What every enrolled job must contain. Each entry names the step and the
#: failure it prevents — an entry with no stated failure gets deleted by the
#: next person who finds it inconvenient.
REQUIRED_STEPS: Dict[str, str] = {
    "actions/setup-python": "without it the job runs on the runner's default interpreter, not the pinned one",
}


def _allowlist() -> dict:
    """Minimal reader for the flat `job: reason` shape this file uses."""
    if not ALLOWLIST.exists():
        return {}
    out = {}
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, reason = line.partition(":")
        out[key.strip()] = reason.strip().strip("\"'")
    return out


def _jobs(path: Path) -> Dict[str, str]:
    """Split a workflow into `job-id -> job text`, by indentation.

    A YAML parser would be more correct and would add a dependency to a check
    that must run on any host. The shape here is fixed enough that indentation
    is sufficient, and a mis-split fails loudly rather than passing wrongly.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return {}

    jobs: Dict[str, List[str]] = {}
    current = None
    for line in lines[start + 1 :]:
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif current and (line.startswith("    ") or not line.strip()):
            jobs[current].append(line)
        elif line.strip() and not line.startswith(" "):
            break
    return {name: "\n".join(body) for name, body in jobs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    allowlist = _allowlist()
    enrolled, findings = [], []

    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for job_id, body in _jobs(workflow).items():
            if not any(pattern.search(body) for pattern in ENROLMENT_PATTERNS):
                continue
            key = f"{workflow.name}:{job_id}"
            enrolled.append(key)
            if key in allowlist:
                continue
            for step, why in REQUIRED_STEPS.items():
                if step not in body:
                    findings.append(f"{key}: missing '{step}' — {why}")

    if args.json:
        emit({"enrolled": enrolled, "findings": findings, "exempt": sorted(allowlist)})

    if findings:
        fail(f"{len(findings)} drift finding(s) across {len(enrolled)} enrolled job(s):")
        for finding in findings:
            item(finding)
        detail()
        detail("Fix the job, or record the divergence in scripts/workflow_drift_allowlist.yaml")
        detail("WITH A REASON. An intended divergence is fine; one nobody decided is the bug.")
        return 1

    ok(f"{len(enrolled)} enrolled job(s) consistent ({len(allowlist)} exempt by allowlist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
