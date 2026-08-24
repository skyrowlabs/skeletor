"""Copy the skeleton into a target directory, substituting @@NAME@@ tokens.

`@@NAME@@` rather than `{{NAME}}` because the skeleton ships Jinja templates,
and a substitution syntax that collides with the templating language of the
thing you are templating is a bug waiting for the first `{{ app_name }}`.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from protogen.spec import Spec

TOKEN_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")

# Copied byte-for-byte. A stray .pyc in the skeleton would otherwise blow up
# the copy with a UnicodeDecodeError.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pyc"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}

SKELETON_DIR = Path(__file__).resolve().parent.parent / "skeleton"


def substitutions(spec: Spec) -> dict[str, str]:
    return {
        "APP_NAME": spec.name,
        "APP_SLUG": spec.slug,
        "APP_PURPOSE": spec.purpose,
        "PORT": str(spec.port),
    }


def render(text: str, values: dict[str, str]) -> str:
    """Substitute every @@TOKEN@@, raising on one we have no value for.

    Strict on purpose: an unknown token would otherwise ship literally into
    somebody's prototype and be discovered by them rather than by us.
    """
    unknown = {m.group(1) for m in TOKEN_RE.finditer(text)} - set(values)
    if unknown:
        raise KeyError(f"unknown placeholder(s): {', '.join(sorted(unknown))}")
    return TOKEN_RE.sub(lambda m: values[m.group(1)], text)


def render_skeleton(spec: Spec, target: Path, skeleton: Path | None = None) -> list[Path]:
    """Materialise the fixed tree. Returns the files written, relative paths."""
    skeleton = skeleton or SKELETON_DIR
    if not skeleton.is_dir():
        raise FileNotFoundError(f"skeleton not found at {skeleton}")
    values = substitutions(spec)
    target.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for src in sorted(skeleton.rglob("*")):
        if any(part in SKIP_DIRS for part in src.relative_to(skeleton).parts):
            continue
        rel = src.relative_to(skeleton)
        dest = target / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in BINARY_SUFFIXES:
            shutil.copyfile(src, dest)
        else:
            dest.write_text(render(src.read_text(), values))
        written.append(rel)
    return written
