"""Where the command stands in for the project in prose, found by masking out code.

The project is {{PROJECT_NAME}}; `{{CLI}}` is what you type. Fences, indented
blocks, inline spans and HTML tags are masked by spaces rather than deleted, so an
offset into the mask is an offset into the file and a finding names a real line.
From sky.boss (`sky-boss/tests/test_naming.py`), which found 368 after a rename.

`tests/test_naming.py` runs this over the tree. The scaffolder runs it over a
fresh render, and leaves both files out when the command is an ordinary word in
the template's own prose, since no mask can tell that word from the command.

    python scripts/prose.py [root]
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path
from typing import Callable, Dict, Iterable, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import fail, item, ok  # noqa: E402

COMMAND = "{{CLI}}"
# The lookarounds exempt every identifier that merely starts with the command's letters.
BARE = re.compile(r"(?<![\w./$-])" + re.escape(COMMAND) + r"(?![\w./-])")

FENCE = re.compile(r"^\s*```")
INDENTED = re.compile(r"^(?: {4,}|\t)\S")
# A backslashed backtick is not a delimiter; reading it as one desynchronises every span after it.
ESCAPED_TICK = re.compile(r"\\`")
CODE_SPAN = re.compile(r"(`+)[\s\S]*?\1")
HTML_TAG = re.compile(r"<[^>]*>", re.DOTALL)
_JS_STRING = re.compile(r"""(?<!\\)(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`)""", re.DOTALL)
_JS_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def _blank(text: str) -> str:
    """Same shape, no content: newlines survive so line numbers do."""
    return "".join("\n" if c == "\n" else " " for c in text)


def _spans_blanked(text: str) -> str:
    neutral = ESCAPED_TICK.sub(r"\\x", text)
    out = list(text)
    for match in CODE_SPAN.finditer(neutral):
        out[match.start() : match.end()] = list(_blank(match.group(0)))
    return "".join(out)


def _markdown_mask(text: str) -> str:
    kept: List[str] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        if FENCE.match(body):
            fenced = not fenced
            kept.append(_blank(line))
            continue
        kept.append(_blank(line) if fenced or INDENTED.match(body) else line)
    mask = _spans_blanked("".join(kept))
    return HTML_TAG.sub(lambda m: _blank(m.group(0)), mask)


def _block_mask(block: str) -> str:
    """A comment or docstring, masked like Markdown, with indentation measured from the block."""
    lines = block.splitlines(keepends=True)
    bodies = [ln.rstrip("\n") for ln in lines[1:] if ln.strip()]
    base = min((len(b) - len(b.lstrip()) for b in bodies), default=0)
    kept: List[str] = []
    fenced = False
    for i, line in enumerate(lines):
        body = line.rstrip("\n")
        if FENCE.match(body):
            fenced = not fenced
            kept.append(_blank(line))
        elif fenced or (i and INDENTED.match(body[base:])):
            kept.append(_blank(line))
        else:
            kept.append(line)
    return _spans_blanked("".join(kept))


def _python_mask(text: str) -> str:
    """Comments and docstrings: the two places a `.py` file holds prose."""
    starts, offset = [], 0
    for line in text.splitlines(keepends=True):
        starts.append(offset)
        offset += len(line)
    mask = list(_blank(text))

    def reveal(start: int, end: int) -> None:
        mask[start:end] = list(_block_mask(text[start:end]))

    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            reveal(starts[token.start[0] - 1] + token.start[1], starts[token.end[0] - 1] + token.end[1])
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            end_line, end_col = first.end_lineno or first.lineno, first.end_col_offset or 0
            reveal(starts[first.lineno - 1] + first.col_offset, starts[end_line - 1] + end_col)
    return "".join(mask)


def _javascript_mask(text: str) -> str:
    """Comments only. Strings are blanked first, because a URL's `//` does not start one."""
    without_strings = _JS_STRING.sub(lambda m: _blank(m.group(0)), text)
    mask = list(_blank(text))
    for match in _JS_COMMENT.finditer(without_strings):
        mask[match.start() : match.end()] = list(_block_mask(text[match.start() : match.end()]))
    return "".join(mask)


MASKS: Dict[str, Callable[[str], str]] = {
    ".md": _markdown_mask,
    ".py": _python_mask,
    ".js": _javascript_mask,
    ".cjs": _javascript_mask,
    ".mjs": _javascript_mask,
}

#: What a walk of a bare render skips; inside a checkout, git decides instead.
_NOT_PROSE = {".git", ".venv", "node_modules", "tmp", "__pycache__"}


def offences(path: Path, root: Path) -> List[str]:
    """Every `path:line` where the command stands in for the project."""
    mask = MASKS[path.suffix](path.read_text(encoding="utf-8"))
    rel = path.relative_to(root)
    return [f"{rel}:{mask.count(chr(10), 0, m.start()) + 1}" for m in BARE.finditer(mask)]


def prose_files(root: Path) -> Iterable[Path]:
    for suffix in MASKS:
        for path in sorted(root.rglob(f"*{suffix}")):
            if not _NOT_PROSE & set(path.relative_to(root).parts):
                yield path


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    found = [hit for path in prose_files(root) for hit in offences(path, root)]
    if not found:
        ok(f"`{COMMAND}` appears in prose only inside code")
        return 0
    fail(f"`{COMMAND}` stands in for {{PROJECT_NAME}} in {len(found)} place(s):")
    for hit in found:
        item(hit)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
