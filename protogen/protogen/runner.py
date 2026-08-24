"""Subprocess execution, behind an interface.

Every docker call in protogen goes through a `Runner`. That is what lets the
verify loop and the repair loop be tested without a Docker daemon -- which
matters more than it sounds, because those two are the parts most likely to
be wrong and the parts an end-to-end test is least likely to cover.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr.strip() else "")).strip()

    def describe(self) -> str:
        return f"$ {' '.join(self.argv)}\n{self.output}"


class Runner(Protocol):
    def run(
        self, argv: list[str], cwd: Path | None = None, timeout: float | None = None
    ) -> CommandResult: ...


class SubprocessRunner:
    def run(
        self, argv: list[str], cwd: Path | None = None, timeout: float | None = None
    ) -> CommandResult:
        try:
            proc = subprocess.run(  # noqa: S603 -- argv is built by us, never by the model
                argv,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return CommandResult(argv, 127, "", f"{argv[0]}: not found")
        except subprocess.TimeoutExpired as exc:
            # A timeout is a result, not an exception: the loop needs the
            # partial output to decide whether the build is slow or hung.
            return CommandResult(
                argv,
                124,
                _text(exc.stdout),
                _text(exc.stderr) + f"\n[timed out after {timeout}s]",
            )
        return CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)


def _text(value: object) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def docker_available(runner: Runner) -> tuple[bool, str]:
    """Whether we can actually run anything. Checked up front, because
    discovering it after the generation passes have run wastes the tokens."""
    if shutil.which("docker") is None:
        return False, "docker is not installed or not on PATH"
    result = runner.run(["docker", "info"], timeout=20)
    if not result.ok:
        return False, "the docker daemon is not reachable (`docker info` failed)"
    compose = runner.run(["docker", "compose", "version"], timeout=20)
    if not compose.ok:
        return False, "`docker compose` is unavailable (needs Compose v2)"
    return True, "docker ok"
