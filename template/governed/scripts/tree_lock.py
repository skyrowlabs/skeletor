#!/usr/bin/env python3
"""Advisory holds on the shared working tree.

Advisory, not enforcing, and that is a decision rather than a limitation: a lock
that can refuse the owner's own interactive command is a lock people learn to
route around, and a routed-around lock protects nothing while looking like it
protects everything.

What it does instead is make "is somebody working here" *answerable*, so the
things that can safely refuse — scheduled jobs, branch resets, `{{CLI}} commit` — have
a fact to refuse on.

Two hold kinds, because they make different things unsafe:

    suite   a test run or stack job: writes under mounted paths, AND the branch
    edit    an editing session or a commit: the branch only

The `edit` kind exists because the incident this came from had no suite running
— just an editor and a `git checkout`. A clean `git status` is not evidence that
nobody is working here.

Stdlib only: this is imported by host-side jobs that must not grow dependencies.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, List, Optional

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import fail, item, ok  # noqa: E402
from scripts.paths import PROJECT_ROOT, TMP_DIR  # noqa: E402

LOCK_DIR = TMP_DIR / "tree-locks"

#: A hold older than this with a live pid is still honoured — long jobs exist.
#: This bound is only for records whose process is gone AND which are old enough
#: that a pid reuse would be a coincidence rather than the same job.
STALE_AFTER_S = 6 * 60 * 60


@dataclass
class Hold:
    kind: str  # "suite" | "edit"
    pid: int
    branch: str
    owner: str  # what took it — a job name, a command, a session id
    started: float

    @property
    def age_s(self) -> float:
        return time.time() - self.started

    @property
    def alive(self) -> bool:
        try:
            os.kill(self.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Another user's process with this pid: it exists, so honour it.
            return True


def _branch() -> Optional[str]:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(PROJECT_ROOT), capture_output=True, text=True
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def _path(pid: int, kind: str) -> Path:
    return LOCK_DIR / f"{kind}-{pid}.json"


def sweep() -> int:
    """Drop records whose process is gone. A crashed holder must never wedge
    the tree — an unattended system that can deadlock itself gets switched off."""
    removed = 0
    for path in LOCK_DIR.glob("*.json"):
        try:
            hold = Hold(**json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, OSError):
            path.unlink(missing_ok=True)
            removed += 1
            continue
        if not hold.alive and hold.age_s > 60:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def holders() -> List[Hold]:
    """Every live hold on this tree, newest first."""
    sweep()
    out = []
    for path in LOCK_DIR.glob("*.json"):
        try:
            out.append(Hold(**json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError, OSError):
            continue
    return sorted((h for h in out if h.alive), key=lambda h: -h.started)


def acquire(kind: str, owner: str) -> Optional[Path]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    branch = _branch()
    hold = Hold(kind=kind, pid=os.getpid(), branch=branch or "", owner=owner, started=time.time())
    path = _path(hold.pid, kind)
    path.write_text(json.dumps(asdict(hold), indent=2), encoding="utf-8")
    return path


def release(kind: str) -> None:
    _path(os.getpid(), kind).unlink(missing_ok=True)


@contextlib.contextmanager
def held(kind: str, owner: str) -> Iterator[None]:
    acquire(kind, owner)
    try:
        yield
    finally:
        release(kind)


def would_strand(branch: str) -> Optional[str]:
    """Why switching this tree to ``branch`` is unsafe, or ``None``.

    Ignores our own pid and stale records. **Refuses on a branch it cannot
    read**: a false refusal costs one retry, a false clearance costs somebody's
    uncommitted work, so the asymmetry decides the default.
    """
    current = _branch()
    if current is None:
        return "cannot read the current branch — refusing rather than guessing"
    if current == branch:
        return None

    mine = os.getpid()
    for hold in holders():
        if hold.pid == mine:
            continue
        return (
            f"{hold.owner} (pid {hold.pid}, {hold.kind} hold, {int(hold.age_s // 60)}m) "
            f"is holding this tree on '{hold.branch or current}'"
        )

    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(PROJECT_ROOT), capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        # Uncommitted work with no recorded hold is still somebody's work — a
        # hold is advisory, so its absence proves nothing.
        return f"the tree has {len(dirty.splitlines())} uncommitted change(s) and no recorded holder"

    return None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        target = sys.argv[2] if len(sys.argv) > 2 else "{{BASE_BRANCH}}"
        reason = would_strand(target)
        if reason:
            fail(f"cannot move to '{target}': {reason}")
        else:
            ok(f"safe to move to '{target}'")
        raise SystemExit(1 if reason else 0)

    live = holders()
    if not live:
        ok("no holds on this tree")
    for hold in live:
        item(f"{hold.kind:<6} pid {hold.pid:<7} {int(hold.age_s // 60):>4}m  {hold.owner}  [{hold.branch}]")
