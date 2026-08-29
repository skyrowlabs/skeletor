"""The record does not live in the checkout, and one module says where it does.

Both halves of this fail silently, which is the only reason they are worth a
test. State written under `tmp/` survives until the first `git clean -fdx` and
then does not — nothing raises, the ledger is simply empty and every job looks
like it has never run. And a *second* definition of the state root is the
defect that reads as correct in review: point the writer at one path and a
reader at another and the suite still passes, because each half is internally
consistent. It proves nothing, and it proves it in green.

See AGENTS.md Critical Rule 14 and `scripts/paths.py::state_dir`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import CLI_DIR, PROJECT_ROOT, SCRIPTS_DIR, STATE_SLUG, state_dir  # noqa: E402
from scripts.reporting.run_ledger import ledger_path  # noqa: E402

#: The one module allowed to name the root. Everything else asks it.
RESOLVER = SCRIPTS_DIR / "paths.py"

#: What a second definition looks like: the directory name, or the environment
#: variable, written somewhere that is not the resolver.
ROOT_TOKENS = re.compile(r"sl-agent-logs|SL_AGENT_LOGS")


def _sources():
    for base in (CLI_DIR, SCRIPTS_DIR):
        for path in sorted(base.rglob("*.py")):
            if path != RESOLVER:
                yield path


def test_state_lives_outside_the_checkout():
    """The whole point. A path under the repo is not state, it is scratch."""
    resolved = state_dir()
    assert PROJECT_ROOT not in resolved.parents and resolved != PROJECT_ROOT, (
        f"state_dir() resolved to {resolved}, which is inside the checkout — " "one `git clean -fdx` from gone"
    )


def test_the_slug_is_not_the_directory_name():
    """A linked worktree's directory is not the slug.

    Deriving it from `PROJECT_ROOT.name` works in the primary checkout and
    gives every pool tree a private state root of its own — the exact
    scattering this layout exists to end, visible only from a tree nobody
    runs the suite in.
    """
    assert STATE_SLUG and "{" not in STATE_SLUG, "STATE_SLUG was never substituted"
    assert state_dir().name == STATE_SLUG


def test_the_override_is_honoured_when_the_path_is_used(monkeypatch, tmp_path):
    """A constant would freeze this at import, and the knob would be a comment."""
    monkeypatch.setenv("SL_AGENT_LOGS", str(tmp_path))
    assert state_dir("ledger").parent == tmp_path / STATE_SLUG


def test_the_ledger_goes_through_the_resolver(monkeypatch, tmp_path):
    """Not merely 'is outside the repo' — actually derived from `state_dir`."""
    monkeypatch.setenv("SL_AGENT_LOGS", str(tmp_path))
    assert ledger_path().is_relative_to(tmp_path / STATE_SLUG)


def test_nothing_else_names_the_state_root():
    """The second definition. This is the test that earns its keep."""
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)}:{n}"
        for path in _sources()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ROOT_TOKENS.search(line)
    ]
    assert not offenders, (
        "The state root is named outside scripts/paths.py:\n  "
        + "\n  ".join(offenders)
        + "\n\nAsk `state_dir()` instead. Two definitions stay consistent right up "
        "until one of them moves, and the suite cannot see the difference."
    )
