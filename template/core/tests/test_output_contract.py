"""The output contract, tested by running the programs — not by reading them.

`scripts/check_output_discipline.py` checks the *shape* of the source. This
checks the *behaviour*, which is the half that actually matters to a caller:

* every `scripts/check_*.py` answers `--json` with something a parser can read
* nothing else lands on that stdout — the explanation goes to stderr

Those are two separate failures. A script can grow a correct payload and still
be unusable because a `⚠️` line shares the stream with it, which is exactly what
had happened to three of them before `scripts/output.py` existed.

Enrolment is by pattern: any `scripts/check_*.py` is covered by existing. A new
checker that forgets `--json` fails here without anybody adding it to a list.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import STATE_SYMBOLS  # noqa: E402
from scripts.paths import PROJECT_ROOT, SCRIPTS_DIR  # noqa: E402


def _checkers():
    return sorted(SCRIPTS_DIR.glob("check_*.py"))


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_there_are_checkers_to_check():
    """A glob that silently matches nothing is a test that always passes."""
    assert _checkers(), "no scripts/check_*.py found — the enrolment pattern is wrong"


@pytest.mark.parametrize("script", _checkers(), ids=lambda p: p.name)
def test_json_payload_parses(script: Path):
    """`--json` puts a parseable object on stdout, whatever the verdict."""
    result = _run(script, "--json")
    assert result.stdout.strip(), f"{script.name} --json wrote nothing to stdout (stderr: {result.stderr[-400:]})"
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), f"{script.name} --json emitted {type(payload).__name__}, not an object"


@pytest.mark.parametrize("script", _checkers(), ids=lambda p: p.name)
def test_status_lines_stay_off_stdout(script: Path):
    """A status symbol on stdout is what makes `--json | jq` fail."""
    result = _run(script, "--json")
    for symbol in STATE_SYMBOLS.values():
        assert symbol.strip() not in result.stdout, (
            f"{script.name} wrote '{symbol.strip()}' to stdout — status lines belong on stderr. "
            "See docs/rules/output.md."
        )


def test_the_human_half_still_happens():
    """The split must not have made a check silent.

    A check whose narration went to a stream nobody reads is worse than one that
    is noisy: it reports nothing and passes.
    """
    result = _run(SCRIPTS_DIR / "check_doc_tables.py")
    assert result.stderr.strip(), "check_doc_tables.py said nothing to a human"
    assert any(symbol.strip() in result.stderr for symbol in STATE_SYMBOLS.values())
