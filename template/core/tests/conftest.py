"""Shared fixtures and the environment-gate helper.

The one rule worth reading before writing a test: **a skip in CI is a failure**.
CI guarantees the environment, so "the service was not reachable" there means
the harness broke — and a harness that silently skips its whole suite reports
green, which is the single most expensive failure mode a test suite has.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Bootstrap only, and it runs before any test module is collected: put the
# package on sys.path so tests can import `scripts.paths`, which owns every
# path in the tree. A bare `pytest tests/` otherwise gets only `tests/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Set by CI and by `{{CLI}} test --ci`. Under it, an env-gate skip becomes a failure.
CI_FLAG = "{{CI_ENV_VAR}}"


def in_ci() -> bool:
    return os.environ.get(CI_FLAG) == "1"


def require_or_skip(condition: bool, reason: str, *, requires: str | None = None) -> None:
    """Skip locally, **fail** in CI.

    Use for anything CI guarantees — services running, seed data present, a
    toolchain installed. Raw ``pytest.skip`` stays legitimate for genuine
    cross-environment conditions CI does not guarantee (a GPU, a paid API key).

        require_or_skip(services_up, "the app is not reachable", requires="services")
    """
    if condition:
        return
    detail = f"{reason} (requires: {requires})" if requires else reason
    if in_ci():
        pytest.fail(f"environment gate failed in CI: {detail}. CI guarantees this — the harness is broken.")
    pytest.skip(detail)


@pytest.fixture(scope="session")
def repo_root():
    """The project root, from the module that owns it — never re-derived here.

    A fixture that works this out for itself is a second answer to a question
    with one owner, and it is the answer a test would trust. See
    `scripts/paths.py`.
    """
    from scripts.paths import PROJECT_ROOT

    return PROJECT_ROOT


@pytest.fixture(autouse=True)
def _never_the_users_state(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the state root at a fresh directory for every test.

    Unset, it falls back to the user's real state under the home directory, so a
    test that forgot it would write there. A test that sets its own still wins,
    because autouse fixtures run first. stash.flow's incident: `stash-flow@c5544b3`.
    """
    from scripts.paths import STATE_ROOT_ENV

    monkeypatch.setenv(STATE_ROOT_ENV, str(tmp_path_factory.mktemp("state-root")))


@pytest.fixture(autouse=True)
def _never_the_users_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail a test that would open the user's real browser.

    A test that means to open one replaces it with a recorder, which wins
    because it is patched later. stash.flow's incident: `stash-flow@a2fe3b7`.
    """
    import webbrowser

    def refuse(name: str):
        def refused(*args, **kwargs):
            raise AssertionError(f"a test reached the real webbrowser.{name}{args!r}; replace it with a recorder")

        return refused

    for name in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, name, refuse(name))

