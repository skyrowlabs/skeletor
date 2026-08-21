"""Shared helpers for the CLI package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def absolutize_path_env() -> None:
    """Make every ``PATH`` entry absolute before anything spawns a child.

    A relative entry — the ``PATH=.venv/bin:$PATH`` prefix people write by hand —
    is re-resolved against *each process's own cwd*. An interpreter found through
    one keeps that relative path as ``sys.executable``, so every child that
    chdirs (a test running from a tmp dir, a subprocess with ``cwd=``) loses it.
    The failure looks like a missing package, which sends you to the wrong place.
    """
    entries = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            entry = os.getcwd()  # POSIX reads an empty entry as the cwd
        entries.append(entry if os.path.isabs(entry) else os.path.abspath(entry))
    os.environ["PATH"] = os.pathsep.join(entries)


def run(cmd: Sequence[str], *, cwd: Optional[Path] = None, check: bool = False, capture: bool = False):
    """Run a command from the project root, echoing it unless capturing."""
    if not capture:
        print(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd or PROJECT_ROOT),
        check=check,
        text=True,
        capture_output=capture,
    )


def script(name: str, *args: str) -> int:
    """Run a repo script with the interpreter running this CLI."""
    return run([sys.executable, str(PROJECT_ROOT / name), *args]).returncode


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=False
    ).stdout.strip()


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def ok(message: str) -> None:
    print(f"✅ {message}")


def fail(message: str) -> None:
    print(f"❌ {message}", file=sys.stderr)


def warn(message: str) -> None:
    print(f"⚠️  {message}", file=sys.stderr)


def summarize(results: Iterable[tuple]) -> int:
    """Print a pass/fail table for a set of gates and return the exit code.

    Every gate runs even when an earlier one failed. A pre-push check that stops
    at the first red gives you one fix per round trip; the whole point is to
    learn everything that is wrong in a single run.
    """
    results = list(results)
    print("\n" + "─" * 60)
    for name, code in results:
        print(f"{'✅' if code == 0 else '❌'}  {name}")
    failed = [name for name, code in results if code != 0]
    print("─" * 60)
    if failed:
        fail(f"{len(failed)} gate(s) failed: {', '.join(failed)}")
        return 1
    ok(f"all {len(results)} gates passed")
    return 0
