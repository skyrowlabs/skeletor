"""``{{CLI}} check`` — every gate, runnable locally.

The organising rule: **anything CI blocks on must be runnable here, with the same
invocation.** A gate you can only observe by pushing costs a round trip per fix,
and the fix rate then depends on how patient you are rather than on how wrong
the code is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from cli.helpers import PROJECT_ROOT, fail, ok, run, script, summarize

DOCS_DIR = PROJECT_ROOT / "docs"


@click.group()
def check() -> None:
    """Validation gates — lint, docs, types, and the pre-push bundle."""


@check.command()
def lint() -> None:
    """The blocking lint set for this project's languages."""
    sys.exit(_lint())


def _lint() -> int:
    results = []
    if (PROJECT_ROOT / ".flake8").exists():
        results.append(("flake8 (errors)", run(["flake8", ".", "--select=E9,F63,F7,F82,F401", "--show-source"]).returncode))
        results.append(("isort", run(["isort", "--check-only", "--diff", "."]).returncode))
        results.append(("black", run(["black", "--check", "."]).returncode))
    if (PROJECT_ROOT / "pyrightconfig.json").exists():
        results.append(("pyright", run(["pyright", "--project", "pyrightconfig.json"]).returncode))
    if (PROJECT_ROOT / "eslint.config.js").exists():
        results.append(("eslint", run(["npm", "run", "lint:check"]).returncode))
    if not results:
        fail("no linters configured — add .flake8 / pyrightconfig.json / eslint.config.js")
        return 1
    return summarize(results)


@check.command(name="docs")
def docs_cmd() -> None:
    """Every documentation gate: indexes, tables, links, refs, report anchors."""
    sys.exit(_docs())


def _docs() -> int:
    return summarize(
        [
            ("generated indexes", script("scripts/docs/regen.py", "--check")),
            ("doc index tables", script("scripts/check_doc_tables.py")),
            ("doc links", script("scripts/check_doc_links.py")),
            ("source → doc refs", script("scripts/check_source_doc_refs.py")),
            ("report anchors", script("scripts/docs/release_window.py", "--check")),
        ]
    )



@check.command(name="doc-links")
@click.option("--fix", is_flag=True, help="repoint fragments with exactly one matching heading")
def doc_links(fix: bool) -> None:
    """Relative markdown links between docs, and their `#fragments`."""
    sys.exit(script("scripts/check_doc_links.py", *(["--fix"] if fix else [])))


@check.command(name="doc-refs")
def doc_refs() -> None:
    """`docs/*` paths cited from source comments — the direction nothing else checks."""
    sys.exit(script("scripts/check_source_doc_refs.py"))


@check.command()
def reports() -> None:
    """Every in-flight report carries a valid, consistent release anchor."""
    sys.exit(script("scripts/docs/release_window.py", "--check"))


@check.command(name="merge-drivers")
def merge_drivers() -> None:
    """Are the generated-docs merge drivers installed in this checkout?

    The driver definition lives in `.git/config`, which is not version
    controlled — so a fresh clone has `.gitattributes` pointing at a driver that
    does not exist, and git silently falls back to a three-way text merge of a
    100k-line generated JSON. That resolution is never correct.
    """
    sys.exit(script("scripts/git/install_merge_drivers.py", "--check"))


@check.command(name="pre-push")
@click.option("--quick", is_flag=True, help="lint and docs only — skip the test suites")
def pre_push(quick: bool) -> None:
    """Everything CI blocks on, in the order that fails fastest.

    Lint first because it is seconds and catches most of what CI would reject;
    tests last because they are the expensive half. Every gate still runs even
    after one fails — one fix per round trip is the thing this exists to avoid.
    """
    results = [("lint", _lint()), ("docs", _docs())]
    if not quick:
        results.append(("unit tests", script("-m", "pytest", "tests/", "-m", "unit", "-q")))
    sys.exit(summarize(results))


@check.command()
def health() -> None:
    """Is the local stack up and answering?"""
    # SCAFFOLD: replace with this project's real health probes.
    ok("nothing to probe yet — wire this to the project's services")
