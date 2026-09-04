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

An entry is also checked against the job it names. A reason makes an exemption a
decision; it does not keep the decision true. One whose job no longer diverges
has outlived its reason, and one whose job is gone is worse — the name can come
back for something else and arrive already exempt.

Usage:  python scripts/check_workflow_drift.py [--json]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import detail, emit, fail, item, ok  # noqa: E402
from scripts.paths import GITHUB_DIR, SCRIPTS_DIR  # noqa: E402

WORKFLOWS = GITHUB_DIR / "workflows"
ALLOWLIST = SCRIPTS_DIR / "workflow_drift_allowlist.yaml"

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


def key_for(workflow: str, job_id: str) -> str:
    """The name a job is known by, here and in the allowlist.

    One function so the checker and the reader cannot disagree about it. They
    did: the key contains a colon and the reader split on the first one, so
    `ci.yml:integration: reason` parsed to the key `ci.yml` and matched nothing
    the checker ever asked about. **The documented escape hatch could not exempt
    a single job**, and a fresh tree could not show it — no enrolled jobs, an
    empty allowlist, green. It surfaces only the day somebody needs to record a
    deliberate divergence, discovers the check will not be quiet, and deletes
    the check.
    """
    return f"{workflow}:{job_id}"


def _allowlist() -> dict:
    """Minimal reader for the flat `key: reason` shape this file uses.

    Split on the first colon **followed by whitespace**, because the key itself
    contains a colon (see `key_for`) and the reason may contain several.
    """
    if not ALLOWLIST.exists():
        return {}
    out = {}
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(.*?):\s+(.*)$", line)
        if not match:
            continue
        out[match.group(1).strip()] = match.group(2).strip().strip("\"'")
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
    # What each exempt job is actually missing, so an entry can be asked whether
    # it is still describing something. Collected for every enrolled job rather
    # than only the unexempt ones — the exempt ones are the whole question.
    divergence: Dict[str, List[str]] = {}

    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for job_id, body in _jobs(workflow).items():
            if not any(pattern.search(body) for pattern in ENROLMENT_PATTERNS):
                continue
            key = key_for(workflow.name, job_id)
            enrolled.append(key)
            missing = [f"{key}: missing '{step}' — {why}" for step, why in REQUIRED_STEPS.items() if step not in body]
            divergence[key] = missing
            if key not in allowlist:
                findings.extend(missing)

    # An exemption is a decision record, and nothing kept the decision current.
    # An entry whose job was fixed has outlived its reason; one whose job is
    # gone is worse — the job name can come back for something else and arrive
    # already exempt, which is an exemption nobody chose.
    stale = [
        f"{key}: allowlisted, but {'no enrolled job by that name' if key not in divergence else 'it no longer diverges'}"
        for key in sorted(allowlist)
        if key not in divergence or not divergence[key]
    ]
    findings.extend(stale)

    if args.json:
        emit({"enrolled": enrolled, "findings": findings, "exempt": sorted(allowlist), "stale": stale})

    if findings:
        fail(f"{len(findings)} drift finding(s) across {len(enrolled)} enrolled job(s):")
        for finding in findings:
            item(finding)
        detail()
        detail("Fix the job, or record the divergence in scripts/workflow_drift_allowlist.yaml")
        detail("WITH A REASON. An intended divergence is fine; one nobody decided is the bug.")
        if stale:
            detail("A stale entry is deleted, not re-justified: what it recorded is gone, so it")
            detail("now exempts a job nobody decided to exempt.")
        return 1

    ok(f"{len(enrolled)} enrolled job(s) consistent ({len(allowlist)} exempt by allowlist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
