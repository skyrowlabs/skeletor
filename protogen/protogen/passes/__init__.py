"""Passes.

Each pass module exports:

    NAME     str
    WRITES   tuple[str, ...]   -- paths it is allowed to produce
    SCHEMA   dict              -- JSON Schema for its structured output
    build(spec, ctx)           -> (system_prompt, user_prompt)
    offline(spec, ctx)         -> dict matching SCHEMA

Two implementations of every pass is the design, not duplication: `build` is
checked against `offline` by the test suite, and a pass whose prompt asks for
something the baseline cannot express has no worked example.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from protogen.files import GeneratedFile, write_all
from protogen.llm import LLM
from protogen.spec import Spec


@dataclass
class PassContext:
    """What a pass can see: the project on disk, and what earlier passes said.

    Later passes read the *real generated source* rather than a description of
    it. A routes pass told "there is a Trip model" will invent a field name;
    one handed models.py will not.
    """

    project_dir: Path
    notes: dict[str, str] = field(default_factory=dict)
    # Free-text instruction for an incremental change (`proto add`).
    change: str = ""
    # A formatted VerifyResult, set only when the repair pass is running.
    failure: str = ""

    def read(self, rel: str) -> str:
        path = self.project_dir / rel
        return path.read_text() if path.exists() else ""

    def sources(self, *rels: str) -> str:
        """Format existing files for a prompt, skipping ones not yet written."""
        chunks = []
        for rel in rels:
            body = self.read(rel)
            if not body.strip():
                continue
            lang = "html" if rel.endswith(".html") else "python"
            chunks.append(f"### `{rel}`\n\n```{lang}\n{body}\n```")
        return "\n\n".join(chunks)

    def template_files(self) -> list[str]:
        root = self.project_dir / "app" / "templates"
        if not root.is_dir():
            return []
        return sorted(
            f"app/templates/{p.name}" for p in root.glob("*.html") if p.name != "base.html"
        )


@dataclass
class PassResult:
    name: str
    files: list[Path]
    notes: str


def run_pass(
    module: ModuleType, spec: Spec, ctx: PassContext, llm: LLM
) -> PassResult:
    """Produce a pass's files and write them, or raise."""
    if llm.offline:
        data = module.offline(spec, ctx)
    else:
        system, user = module.build(spec, ctx)
        data = llm.structured(
            system=system, user=user, schema=module.SCHEMA, label=module.NAME
        )
    files = [GeneratedFile(path=f["path"], content=f["content"]) for f in data["files"]]
    written = write_all(ctx.project_dir, files, module.NAME)
    notes = data.get("notes", "")
    ctx.notes[module.NAME] = notes
    return PassResult(name=module.NAME, files=written, notes=notes)
