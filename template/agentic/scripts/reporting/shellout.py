"""Shell out without letting an absent tool crash the job.

Every caller here already branches on `returncode`: a collector returns `""`, a
check reports the tool as unavailable. That branch is unreachable when the binary
is missing, because `subprocess.run` raises `FileNotFoundError` before any
`returncode` exists — and cron's `PATH` is exactly where a tool goes missing.

So the failure is translated into what callers already read: a non-zero result,
with the shell's own codes. `tests/test_reporting_shellout.py` requires every
subprocess call in the reporting code to come through here or handle the
exception itself, over a discovered population, so a job added later is covered.

Ported from jam.sense (`jam-sense@982042d7e`), where 20 of 64 call sites had it.
"""

from __future__ import annotations

import subprocess
from typing import Any, Sequence

#: "command not found", as a POSIX shell reports it.
MISSING = 127

#: What `timeout(1)` returns for a command it killed.
TIMED_OUT = 124


def run(argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """`subprocess.run(argv, **kwargs)`, except a missing tool or a hang is a result.

    The synthesized results carry `""` rather than `None` on both streams, so a
    caller's error branch can read them whether or not it asked to capture.
    """
    argv = list(argv)
    try:
        return subprocess.run(argv, **kwargs)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(argv, MISSING, "", f"{exc.filename or argv[0]}: not on PATH")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, TIMED_OUT, "", f"timed out after {kwargs.get('timeout')}s")
