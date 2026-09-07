"""The shell's package, reached through its discovered name.

`cli` is the most collided-with package name in a python monorepo, so
`--shell-package` renames it — and **no file in this tree spells the result**.
The package finds its own command groups through `__name__` and `__path__`,
`__main__.py` imports relatively, `scripts/paths.py` finds the directory by its
`__main__.py`, and the tests come here.

## Why this is a module and not six `importlib` calls

Six call sites needed the same two lines, and a convention you have to remember
to apply is a registry with no enforcement. It is also the difference between a
rename that works and one that half-works: a static `from cli.test_cmds import
SUITES` is the single thing a rename cannot survive, and it fails at collection
time with `ModuleNotFoundError`, which reads as a broken tree rather than as a
missed site.

## And why the name is discovered rather than substituted

The generator could have written the name into every file. It cannot: a
placeholder works in a string literal and **not** in an import statement, where
`from <token>.x import y` is a syntax error — so the template's own python would
stop parsing, and several of the generator's checks read that python with `ast`.
Discovery keeps the property and costs one indirection.

(This paragraph deliberately does not spell the placeholder. The generator
substitutes every occurrence of one, including inside the sentence explaining
why it does not — which is the same trick as a detector that assembles its own
needle rather than containing it.)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import SHELL_PACKAGE  # noqa: E402

__all__ = ["SHELL_PACKAGE", "module", "group"]


def module(name: str = "") -> ModuleType:
    """The shell package, or one module inside it."""
    return importlib.import_module(f"{SHELL_PACKAGE}.{name}" if name else SHELL_PACKAGE)


def group():
    """The root click group.

    Named `cli` inside the package whatever the package is called — the group
    and the directory shared a name once, and only the directory moves. That is
    the artefact sky.boss's own rename produced: a `sed` over `from cli import
    cli` gave `from x import x`, renaming the group as well.
    """
    return module().cli
