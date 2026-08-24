"""Boot the app, wait for it, run its smoke tests, capture the logs.

This is the part of protogen that decides whether a tree gets handed back.
Generation is the easy half; "workable running app" is this file.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from protogen.runner import CommandResult, Runner

# Stages, in the order they can fail. The stage name is what the repair pass
# is told, and a repair prompt for "the image would not build" is a different
# prompt from one for "the create test asserted 2 == 1".
STAGES = ("build", "health", "tests")


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    stage: str
    summary: str
    output: str = ""
    logs: str = ""

    def report(self) -> str:
        parts = [f"[{self.stage}] {self.summary}"]
        if self.output.strip():
            parts.append("--- command output ---\n" + self.output.strip())
        if self.logs.strip():
            parts.append("--- container logs ---\n" + self.logs.strip())
        return "\n\n".join(parts)


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 -- connection refused while booting
        return 0, str(exc)


class Verifier:
    """All docker interaction lives here, behind an injected Runner."""

    def __init__(
        self,
        project_dir: Path,
        port: int,
        runner: Runner,
        getter: Callable[[str, float], tuple[int, str]] = http_get,
        sleep: Callable[[float], None] = time.sleep,
        health_timeout: float = 180.0,
        build_timeout: float = 900.0,
    ) -> None:
        self.project_dir = Path(project_dir)
        self.port = port
        self.runner = runner
        self.getter = getter
        self.sleep = sleep
        self.health_timeout = health_timeout
        self.build_timeout = build_timeout

    def compose(self, *args: str, timeout: float | None = None) -> CommandResult:
        return self.runner.run(
            ["docker", "compose", *args], cwd=self.project_dir, timeout=timeout
        )

    def down(self) -> CommandResult:
        return self.compose("down", "-v", "--remove-orphans", timeout=180)

    def up(self) -> CommandResult:
        # `down -v` first, every time. The schema is created by
        # `create_all()`, which cannot alter an existing table -- so a repair
        # that changed a model would otherwise be verified against the old
        # schema and fail for a reason that has already been fixed.
        self.down()
        return self.compose("up", "-d", "--build", timeout=self.build_timeout)

    def logs(self, tail: int = 200) -> str:
        result = self.compose("logs", "--no-color", f"--tail={tail}", timeout=60)
        return result.output

    def wait_healthy(self) -> tuple[bool, str]:
        url = f"http://localhost:{self.port}/healthz"
        deadline = time.monotonic() + self.health_timeout
        last = "no attempt made"
        while True:
            status, body = self.getter(url, 3.0)
            if status == 200:
                try:
                    if json.loads(body).get("ok") is True:
                        return True, body
                except json.JSONDecodeError:
                    pass
            last = f"HTTP {status}: {body[:400]}"
            if time.monotonic() >= deadline:
                return False, last
            self.sleep(2.0)

    def run_tests(self) -> CommandResult:
        # -T: no TTY. Without it this hangs forever in CI and in any
        # non-interactive shell, which is every shell protogen runs in.
        return self.compose("exec", "-T", "app", "pytest", "-q", timeout=300)

    def verify(self) -> VerifyResult:
        built = self.up()
        if not built.ok:
            return VerifyResult(
                False, "build", "docker compose could not build or start the stack",
                built.describe(),
            )

        healthy, detail = self.wait_healthy()
        if not healthy:
            return VerifyResult(
                False, "health",
                f"/healthz never came up on port {self.port} within "
                f"{self.health_timeout:.0f}s",
                detail, self.logs(),
            )

        tests = self.run_tests()
        if not tests.ok:
            return VerifyResult(
                False, "tests", "the smoke tests failed", tests.describe(), self.logs()
            )

        return VerifyResult(
            True, "tests", f"green -- app is up on http://localhost:{self.port}",
            tests.output,
        )
