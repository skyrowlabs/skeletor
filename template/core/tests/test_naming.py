"""The project's name in prose, its command in code spans. See `scripts/prose.py`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import PROJECT_ROOT  # noqa: E402
from scripts.prose import BARE, COMMAND, MASKS, offences  # noqa: E402
from tests.repo_files import present  # noqa: E402
from tests.scanning import scanned  # noqa: E402


def test_the_command_is_never_the_project_in_prose():
    files = scanned([p for suffix in MASKS for p in present(f"*{suffix}")], "prose-bearing files", least=20)
    found = [hit for path in files for hit in offences(path, PROJECT_ROOT)]
    assert not found, (
        f"`{COMMAND}` used in prose, where {{PROJECT_NAME}} is meant — write the name, "
        f"or put the command in backticks if it is the thing being typed:\n" + "\n".join(found)
    )


def test_the_masks_keep_code_and_reveal_prose():
    spoken = f"type {COMMAND} here"
    assert BARE.search(MASKS[".md"](spoken)), "prose must be seen"
    assert not BARE.search(MASKS[".md"](f"type `{COMMAND} x` here\n\n```\n{COMMAND}\n```\n"))
    assert not BARE.search(MASKS[".py"](f'x = "{COMMAND}"\n')), "a string literal is code"
    assert BARE.search(MASKS[".py"](f"# {spoken}\n")) and BARE.search(MASKS[".js"](f"// {spoken}\n"))


def test_an_unmatched_backtick_run_does_not_hide_what_follows():
    assert BARE.search(MASKS[".md"](f"with a ```bash block\n\nlater {COMMAND} here\n")), "proto.pilot's repro"
    assert not BARE.search(MASKS[".md"](f"with a ```bash block\n\nlater `{COMMAND}`'s surface\n"))
    assert not BARE.search(MASKS[".md"](f"``a `{COMMAND}` b``")), "a longer run closes only on its own length"
