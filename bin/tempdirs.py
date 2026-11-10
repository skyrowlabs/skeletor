"""Temp directories a killed `bin/skeletor-*` run does not leave behind.

An agent's Bash timeout ends a run with SIGTERM, which skips every `finally`, and
archdesk's /tmp is RAM-backed: 11 verify trees, 5.9G, reached swap (jam-sense,
2026-11-10). Two halves, because SIGKILL runs no handler at all:

* `exit_on_signal` turns SIGTERM and SIGHUP into `SystemExit`, so the caller's
  own `finally` removes what it made.
* `owned_tempdir` records the creating pid inside the directory, and
  `sweep_dead` removes a directory whose recorded owner is gone. One with no
  readable owner, or a live one, is never touched.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional

OWNER_FILE = ".skeletor-owner-pid"
#: The name v0.81.9's `bin/skeletor-verify` wrote, still read so its trees are swept.
LEGACY_OWNER_FILES = (".skeletor-verify-pid",)


def exit_on_signal() -> None:
    """SIGTERM and SIGHUP raise `SystemExit(128 + signum)`, so `finally` blocks run."""

    def stop(signum: int, _frame: Any) -> None:
        raise SystemExit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, stop)


def alive(pid: int) -> bool:
    """Whether `pid` names a running process; a process we may not signal is alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def record_owner(directory: Path) -> None:
    """Write this process's pid into `directory`, so a later run can tell when it died."""
    (directory / OWNER_FILE).write_text(f"{os.getpid()}\n", encoding="utf-8")


def owned_tempdir(prefix: str, dir: Optional[Path] = None) -> Path:
    """`tempfile.mkdtemp`, with this process recorded as the owner."""
    made = Path(tempfile.mkdtemp(prefix=prefix, dir=str(dir) if dir else None))
    record_owner(made)
    return made


def _owner(candidate: Path) -> Optional[int]:
    for name in (OWNER_FILE, *LEGACY_OWNER_FILES):
        try:
            return int((candidate / name).read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return None


def sweep_dead(prefix: str, root: Optional[Path] = None, prune: Optional[Path] = None) -> List[Path]:
    """Remove `<root>/<prefix>*` directories whose recorded owner is dead; return them.

    `prune` names a repository whose worktrees lived in those directories, and
    gets `git worktree prune` once anything is removed.
    """
    removed = []
    for candidate in sorted(Path(root or tempfile.gettempdir()).glob(f"{prefix}*")):
        pid = _owner(candidate) if candidate.is_dir() else None
        if pid is not None and pid != os.getpid() and not alive(pid):
            shutil.rmtree(candidate, ignore_errors=True)
            removed.append(candidate)
    if removed and prune is not None:
        subprocess.run(["git", "-C", str(prune), "worktree", "prune"], capture_output=True)
    return removed
