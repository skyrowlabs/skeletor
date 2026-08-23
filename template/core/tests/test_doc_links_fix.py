"""`check_doc_links.py --fix` repoints a fragment, and refuses to guess.

The refusals are the interesting half. A repair tool that is right most of the
time is worse than none: a fragment repointed to the wrong section reads as
correct forever, whereas a dead one announces itself on the next run. So the
cases below pin what it must **decline** to touch as hard as what it fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import check_doc_links as links  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A miniature docs tree the checker treats as the whole repo."""
    (tmp_path / "docs").mkdir()
    monkeypatch.setattr(links, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(links, "IGNORE_FILE", tmp_path / ".validate-ignore")
    monkeypatch.setattr(links, "SCAN_ROOTS", ["docs"])
    monkeypatch.setattr(links, "EXTRA_FILES", [])

    def write(name: str, body: str) -> Path:
        path = tmp_path / "docs" / name
        path.write_text(body, encoding="utf-8")
        return path

    return write


def test_repoints_a_heading_that_grew(tree):
    """The common case: somebody made a heading more specific."""
    source = tree("a.md", "# A\n\nSee [the reason](b.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert links.repoint_fragments() == [
        "docs/a.md: '#why-this-exists' → '#why-this-exists-as-its-own-checker' in docs/b.md"
    ]
    assert "b.md#why-this-exists-as-its-own-checker" in source.read_text(encoding="utf-8")


def test_repoints_a_heading_that_shrank(tree):
    source = tree("a.md", "# A\n\n[x](b.md#testing-rules-for-agents).\n")
    tree("b.md", "# B\n\n## Testing Rules\n")

    assert links.repoint_fragments()
    assert "b.md#testing-rules)" in source.read_text(encoding="utf-8")


def test_refuses_when_two_headings_match(tree):
    """Two candidates means a human chooses. Nothing is written."""
    source = tree("a.md", "# A\n\n[x](b.md#testing).\n")
    tree("b.md", "# B\n\n## Testing Rules\n\n## Testing Budgets\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before


def test_refuses_when_no_heading_matches(tree):
    """The section did not move, it went — that is a sentence to rewrite."""
    source = tree("a.md", "# A\n\n[x](b.md#deleted-entirely).\n")
    tree("b.md", "# B\n\n## Something Unrelated\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before


def test_never_rewrites_a_broken_path(tree):
    """Where a file went is a judgement call, so `--fix` does not make it."""
    source = tree("a.md", "# A\n\n[x](gone.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before
    assert links.scan()[0], "the broken path must still be reported"


def test_leaves_links_inside_code_fences_alone(tree):
    """A link in a fenced example is illustration, not a reference.

    This is what the offset-preserving mask buys: the fix rewrites by position
    in the original text, so a masked region must not be edited *and* must not
    shift the offsets of the links after it.
    """
    source = tree(
        "a.md",
        "# A\n\n```\n[example](b.md#why-this-exists)\n```\n\nReal: [x](b.md#why-this-exists).\n",
    )
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert len(links.repoint_fragments()) == 1
    body = source.read_text(encoding="utf-8")
    assert "[example](b.md#why-this-exists)" in body, "the fenced example was rewritten"
    assert "Real: [x](b.md#why-this-exists-as-its-own-checker)." in body


def test_fixes_a_same_file_fragment(tree):
    source = tree("a.md", "# A\n\n[jump](#the-old-name)\n\n## The Old Name Of This Section\n")

    assert links.repoint_fragments()
    assert "(#the-old-name-of-this-section)" in source.read_text(encoding="utf-8")


def test_fix_is_idempotent(tree):
    """A second run has nothing to do — the first one made the link valid."""
    tree("a.md", "# A\n\n[x](b.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert len(links.repoint_fragments()) == 1
    assert links.repoint_fragments() == []
    assert links.scan() == ([], [])
