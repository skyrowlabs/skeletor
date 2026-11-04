"""Dependabot's config and the workflow that merges its pull requests agree with the rest of the tree."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import GITHUB_DIR  # noqa: E402
from scripts.yaml_text import read_uncommented  # noqa: E402
from tests.scanning import scanned  # noqa: E402
from tests.test_lint_tool_parity import TOOLS  # noqa: E402

CONFIG = GITHUB_DIR / "dependabot.yml"
MERGER = GITHUB_DIR / "workflows" / "dependabot-auto-merge.yml"


def _entries() -> list[str]:
    return re.split(r"^  - package-ecosystem:", read_uncommented(CONFIG), flags=re.MULTILINE)[1:]


def test_every_ecosystem_waits_out_a_cooldown():
    """A hijacked release is usually yanked within days; auto-merge would take it the night it lands."""
    missing = [entry.split()[0] for entry in scanned(_entries(), "dependabot ecosystems") if "cooldown:" not in entry]
    assert not missing, f"ecosystems with no cooldown: {missing}"


def test_the_lint_tools_are_ignored_because_one_file_cannot_bump_them():
    pip = next(entry for entry in scanned(_entries(), "dependabot ecosystems") if entry.split()[0] == "pip")
    ignored = set(re.findall(r"dependency-name:\s*(\S+)", pip))
    assert ignored == set(TOOLS.values()), f"ignored {sorted(ignored)}, lint parity pins {sorted(TOOLS.values())}"


def test_the_merger_runs_after_ci_passes_and_merges_with_the_app_token():
    text = read_uncommented(MERGER)
    ci_name = re.search(r"^name:\s*(.+?)\s*$", read_uncommented(GITHUB_DIR / "workflows" / "ci.yml"), re.MULTILINE)
    assert ci_name and f'workflows: ["{ci_name.group(1)}"]' in text, "it must follow the workflow named in ci.yml"
    assert "workflow_run.conclusion == 'success'" in text
    assert re.search(r"GH_TOKEN:\s*\$\{\{\s*steps\.app-token\.outputs\.token", text), "a GITHUB_TOKEN merge runs no CI"


def test_the_merger_never_checks_out_the_pull_requests_code():
    """It runs with write access; the script it loads must be the default branch's."""
    text = read_uncommented(MERGER)
    # A step's own keys sit deeper than the `- ` that starts the next one.
    checkouts = scanned(re.findall(r"- uses: actions/checkout@[^\n]*\n((?:[ ]{8,}[^\n]*\n)*)", text), "checkouts")
    assert not any("ref:" in block for block in checkouts)
    assert (GITHUB_DIR / "scripts" / "dependabot-hold.cjs").exists()
