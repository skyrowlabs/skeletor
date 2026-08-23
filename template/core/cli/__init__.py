"""{{PROJECT_NAME}} CLI — one entry point for everything you do in this repo.

Implemented as a package of command-group modules, one per domain. The rule that
keeps it useful is in ``AGENTS.md``: **adding or changing a script means updating
this package in the same commit.** A script nobody can discover is a script
nobody runs, and the second person to need it writes it again.
"""

from __future__ import annotations

import subprocess
import sys

# Before the click guard, so the guard can speak in the same voice as everything
# else. `cli.helpers` reaches `scripts/output.py`, which is stdlib-only —
# a dependency-missing message that itself needs a dependency is no message.
from cli.helpers import PROJECT_ROOT, detail, fail

try:
    import click
except ImportError:  # pragma: no cover - dependency guard
    fail("The {{PROJECT_NAME}} CLI requires 'click'.")
    detail("Install with: pip install -r scripts/requirements.txt")
    sys.exit(1)


def get_version() -> str:
    """``git describe`` if we are in a checkout, else the VERSION file.

    ``git describe`` is preferred because it says how far past the tag you are —
    ``v1.4.0-5-gabc1234-dirty`` is the difference between "the released code" and
    "something that looks like it".
    """
    try:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        ).stdout.strip()
        if described:
            return described
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    version_file = PROJECT_ROOT / "VERSION"
    return version_file.read_text().strip() if version_file.exists() else "unknown"


@click.group()
@click.version_option(version=get_version(), prog_name="{{PROJECT_NAME}}")
def cli() -> None:
    """{{PROJECT_NAME}} — {{TAGLINE}}"""


#: Command groups are DISCOVERED, not listed.
#:
#: A hand-written import list here would be a registry — and the second half of
#: this project's tooling exists because forgetting to update a registry is
#: silent. A module that exports a click Group or Command whose name matches the
#: module (or the documented alias below) is registered by existing, which is the
#: same rule the test suite uses for markers.
#:
#: The alias map is for the few modules whose Python name cannot be the command
#: name (`test` shadows nothing useful; `test_cmds` avoids pytest collection).
_ALIASES = {"test_cmds": "test", "pr_train": "train"}


def _discover() -> None:
    import importlib
    import pkgutil

    import cli as package

    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        name = info.name
        if name.startswith("_") or name == "helpers":
            continue
        module = importlib.import_module(f"cli.{name}")
        command_name = _ALIASES.get(name, name)
        candidate = getattr(module, command_name, None) or getattr(module, name, None)
        if isinstance(candidate, click.Command):
            cli.add_command(candidate, name=command_name)


_discover()
