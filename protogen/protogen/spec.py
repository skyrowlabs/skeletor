"""The spec is the contract between the human, the model, and every pass.

Everything downstream reads this and nothing else about the user's intent.
It is deliberately small: a spec you cannot review in thirty seconds is a
spec nobody reviews, and an unreviewed spec is just the model's first guess
wearing a schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SPEC_FILENAME = "spec.json"
SPEC_DIR = ".protogen"

# Kept small on purpose. Every type here has an unambiguous mapping to a
# SQLAlchemy column, a form input, and a seed-value generator. A type we
# cannot render in all three places is a type that produces a broken app.
FieldType = Literal["str", "text", "int", "float", "bool", "date", "datetime"]

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class Field_(BaseModel):
    """One column on one entity."""

    model_config = {"populate_by_name": True}

    name: str = Field(description="snake_case attribute name")
    type: FieldType = "str"
    required: bool = True
    label: str = ""

    @field_validator("name")
    @classmethod
    def _snake(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"field name must be snake_case: {v!r}")
        if v in {"id", "metadata"}:
            raise ValueError(f"field name {v!r} is reserved")
        return v

    def human_label(self) -> str:
        return self.label or self.name.replace("_", " ").capitalize()


class Entity(BaseModel):
    """One table, one model class, one set of CRUD routes."""

    name: str = Field(description="PascalCase singular, e.g. Trip")
    plural: str = Field(default="", description="snake_case plural, e.g. trips")
    fields: list[Field_] = Field(default_factory=list)
    belongs_to: str | None = Field(
        default=None, description="PascalCase name of the parent entity, or null"
    )

    @field_validator("name")
    @classmethod
    def _pascal(cls, v: str) -> str:
        if not PASCAL_RE.match(v):
            raise ValueError(f"entity name must be PascalCase: {v!r}")
        return v

    def model_post_init(self, __context: object) -> None:
        if not self.plural:
            object.__setattr__(self, "plural", _pluralise(_snake(self.name)))

    @property
    def table(self) -> str:
        return self.plural

    @property
    def var(self) -> str:
        return _snake(self.name)


class Screen(BaseModel):
    """One page. `kind` decides the template shape, not the model's mood."""

    name: str
    path: str = Field(description="URL path, e.g. /trips or /trips/{id}")
    entity: str | None = None
    kind: Literal["list", "detail", "form", "custom"] = "list"

    @field_validator("path")
    @classmethod
    def _leading_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"screen path must start with '/': {v!r}")
        return v


class Spec(BaseModel):
    """The whole app, as far as protogen is concerned."""

    name: str = Field(description="Human-readable app name")
    slug: str = Field(description="snake_case identifier; also the DB name")
    purpose: str = Field(description="One sentence: what this app is for")
    entities: list[Entity] = Field(default_factory=list)
    screens: list[Screen] = Field(default_factory=list)
    auth: Literal["none", "password"] = "none"
    jobs: list[str] = Field(default_factory=list)
    external_apis: list[str] = Field(default_factory=list)
    port: int = 8080
    protogen_version: str = "0.1.0"
    # Free-text direction the user gave, carried through to every pass so
    # "make it feel like a kanban board" survives past intake.
    direction: str = ""

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"slug must be snake_case: {v!r}")
        return v

    # -- persistence ---------------------------------------------------

    @classmethod
    def load(cls, project_dir: Path) -> "Spec":
        path = Path(project_dir) / SPEC_DIR / SPEC_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"no spec at {path} -- is {project_dir} a protogen project?"
            )
        return cls.model_validate_json(path.read_text())

    def save(self, project_dir: Path) -> Path:
        path = Path(project_dir) / SPEC_DIR / SPEC_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2) + "\n")
        return path

    # -- helpers -------------------------------------------------------

    def entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)

    def summary(self) -> str:
        """What gets printed for the human review checkpoint."""
        lines = [f"{self.name} ({self.slug})  ->  port {self.port}", f"  {self.purpose}"]
        if self.direction:
            lines.append(f"  direction: {self.direction}")
        lines.append("  entities:")
        for e in self.entities:
            parent = f" (belongs to {e.belongs_to})" if e.belongs_to else ""
            lines.append(f"    {e.name}{parent}")
            for f in e.fields:
                req = "" if f.required else "?"
                lines.append(f"      {f.name}{req}: {f.type}")
        lines.append("  screens:")
        for s in self.screens:
            lines.append(f"    {s.path:<24} {s.kind:<8} {s.name}")
        lines.append(f"  auth: {self.auth}")
        if self.jobs:
            lines.append(f"  jobs: {', '.join(self.jobs)}")
        if self.external_apis:
            lines.append(f"  external apis: {', '.join(self.external_apis)}")
        return "\n".join(lines)


def _snake(pascal: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", pascal).lower()


def _pluralise(word: str) -> str:
    """Deliberately naive. A wrong plural is a cosmetic bug in a prototype;
    an irregular-noun table is a maintenance burden forever."""
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and not word.endswith(("ay", "ey", "iy", "oy", "uy")):
        return word[:-1] + "ies"
    return word + "s"


def intake_schema() -> dict:
    """JSON Schema handed to the model for the intake pass.

    Generated from the pydantic model rather than hand-written, so a field
    added above cannot silently fail to reach the model.
    """
    schema = Spec.model_json_schema()
    schema = _inline_defs(schema)
    _strictify(schema)
    return schema


def _inline_defs(schema: dict) -> dict:
    """Resolve $ref/$defs into a single self-contained schema.

    The API's json_schema format wants one object; pydantic emits refs.
    """
    defs = schema.pop("$defs", {})

    def walk(node: object) -> object:
        if isinstance(node, dict):
            if "$ref" in node:
                key = node["$ref"].rsplit("/", 1)[-1]
                target = walk(json.loads(json.dumps(defs[key])))
                extra = {k: v for k, v in node.items() if k != "$ref"}
                assert isinstance(target, dict)
                target.update(extra)
                return target
            # anyOf [X, null] -> keep as-is; the API handles union types.
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    result = walk(schema)
    assert isinstance(result, dict)
    return result


def _strictify(node: object) -> None:
    """Every object gets additionalProperties:false and a full `required`.

    Structured output needs this to be strict; and a model that can invent
    a key is a model that will, once, in the pass you did not test.
    """
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = sorted(node["properties"].keys())
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for value in node:
            _strictify(value)
