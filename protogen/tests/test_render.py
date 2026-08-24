from __future__ import annotations

import pytest

from protogen.render import SKELETON_DIR, TOKEN_RE, render, render_skeleton, substitutions


def test_render_substitutes_known_tokens(spec):
    assert render("port @@PORT@@", substitutions(spec)) == "port 8099"


def test_render_raises_on_an_unknown_token(spec):
    # Strict on purpose: an unknown token would otherwise ship literally into
    # somebody's prototype and be found by them rather than by us.
    with pytest.raises(KeyError, match="MYSTERY"):
        render("@@MYSTERY@@", substitutions(spec))


def test_every_skeleton_token_has_a_value(spec):
    values = set(substitutions(spec))
    for path in SKELETON_DIR.rglob("*"):
        if not path.is_file() or path.suffix in {".pyc"}:
            continue
        found = {m.group(1) for m in TOKEN_RE.finditer(path.read_text())}
        assert found <= values, f"{path} uses unknown placeholder(s) {found - values}"


def test_rendered_tree_has_no_placeholders_left(spec, tmp_path):
    written = render_skeleton(spec, tmp_path)
    assert written
    for rel in written:
        body = (tmp_path / rel).read_text()
        assert not TOKEN_RE.search(body), f"{rel} still contains a placeholder"


def test_pycache_is_not_copied(spec, tmp_path):
    render_skeleton(spec, tmp_path)
    assert not list(tmp_path.rglob("__pycache__"))
