"""Test doubles for the two things that need a machine we do not have in CI:
a Docker daemon, and an API key."""

from __future__ import annotations

from pathlib import Path

from protogen.runner import CommandResult


class FakeRunner:
    """Matches argv prefixes to canned results; records every call."""

    def __init__(self, responses: list[tuple[list[str], tuple[int, str, str]]] | None = None):
        self.responses = responses or []
        self.calls: list[list[str]] = []

    def run(self, argv, cwd: Path | None = None, timeout: float | None = None):
        self.calls.append(list(argv))
        for prefix, (code, out, err) in self.responses:
            if argv[: len(prefix)] == prefix:
                return CommandResult(list(argv), code, out, err)
        return CommandResult(list(argv), 0, "", "")

    def ran(self, *fragment: str) -> bool:
        return any(list(fragment) == call[: len(fragment)] for call in self.calls)


class FakeLLM:
    """Returns canned structured responses in order."""

    offline = False

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        self.calls.append({"label": label, "system": system, "user": user})
        if not self.responses:
            raise AssertionError(f"FakeLLM ran out of responses at pass {label!r}")
        return self.responses.pop(0)


class FakeVerifier:
    """Yields a scripted sequence of VerifyResults."""

    def __init__(self, results):
        self.results = list(results)
        self.runs = 0

    def verify(self):
        self.runs += 1
        if not self.results:
            raise AssertionError("FakeVerifier ran out of results")
        return self.results.pop(0)
