"""Idea -> spec.

The only pass whose output is not files. It is also the only human checkpoint
in the whole tool, which is why the spec is small: a spec you cannot read in
thirty seconds is one nobody reads, and an unreviewed spec is just the model's
first guess wearing a schema.
"""

from __future__ import annotations

import re

from protogen.baseline import standard_screens
from protogen.spec import Spec, intake_schema

NAME = "intake"
WRITES: tuple[str, ...] = ()
SCHEMA = intake_schema()

SYSTEM = """\
You turn a one-line product idea into a small, concrete application spec.

You are specifying a PROTOTYPE: something to look at and click through in an
afternoon, not a product. Bias hard toward less.

Rules:

- 1 to 4 entities. If the idea suggests more, pick the ones without which the
  app makes no sense and drop the rest. Two is usually right.
- 2 to 6 fields per entity. No `created_at`/`updated_at` unless the idea is
  actually about time. No status enums with six states; a boolean will do.
- Field types are limited to: str, text, int, float, bool, date, datetime.
  `str` is a single line; `text` is a paragraph.
- At most one `belongs_to` relationship per entity, naming a parent entity in
  the same spec. No many-to-many.
- `auth` is "none" unless the idea is explicitly about accounts or privacy.
- `jobs` and `external_apis` are almost always empty. Only fill them if the
  idea is meaningless without them, and name them, do not describe them.
- `slug` is snake_case and is also the database name.
- Leave `port` at 8080 and `protogen_version` at "0.1.0"; the tool overwrites
  both.
- `direction` echoes back any styling or behavioural steer the user gave, in
  their words. Empty string if they gave none.

Screens: emit exactly this set and nothing else, because the tests and the
routes are generated from it and both must agree.

- one `custom` screen "Home" at "/"
- per entity, in order: a `list` at "/<plural>", a `form` at "/<plural>/new",
  and a `detail` at "/<plural>/{row_id}" -- with the literal braces.

Use the entity's snake_case plural. Prefer the user's own vocabulary for
`name` and for field names: if they say "gig", the entity is Gig, not Event.
"""


def build(spec_or_idea, ctx) -> tuple[str, str]:
    """`spec_or_idea` is the raw idea string for this pass."""
    idea = spec_or_idea if isinstance(spec_or_idea, str) else spec_or_idea.purpose
    user = f"Idea: {idea}\n"
    if ctx.change:
        user += f"\nExtra direction from the user: {ctx.change}\n"
    return SYSTEM, user


def offline(idea: str, ctx) -> dict:
    """The baseline cannot read English. It produces a single-entity app named
    after the idea, which is enough to exercise the pipeline end to end."""
    words = [w for w in re.findall(r"[A-Za-z]+", idea)][:3] or ["Thing"]
    name = " ".join(w.capitalize() for w in words)
    slug = "_".join(w.lower() for w in words)
    entity = words[0].capitalize()
    data = {
        "name": name,
        "slug": slug,
        "purpose": idea.strip() or "A prototype.",
        "entities": [
            {
                "name": entity,
                "plural": "",
                "belongs_to": None,
                "fields": [
                    {"name": "title", "type": "str", "required": True, "label": ""},
                    {"name": "notes", "type": "text", "required": False, "label": ""},
                    {"name": "done", "type": "bool", "required": False, "label": ""},
                ],
            }
        ],
        "screens": [],
        "auth": "none",
        "jobs": [],
        "external_apis": [],
        "port": 8080,
        "protogen_version": "0.1.0",
        "direction": ctx.change,
    }
    data["screens"] = standard_screens(Spec.model_validate(data))
    return data


AMEND_SYSTEM = (
    SYSTEM
    + """

## Amending an existing spec

You are given a spec that already exists and a change the user asked for.
Return the COMPLETE updated spec.

- Change only what the request requires. Keep every existing entity name,
  field name, slug and screen path that the change does not touch -- they are
  already in generated code, in seed data and in the user's head, and a
  gratuitous rename is a rewrite of the whole app.
- Keep `slug` and `port` exactly as they are.
- Regenerate the `screens` list from the same rule as before, so it stays
  consistent with the entities after your change.
"""
)


def build_amend(spec, change: str) -> tuple[str, str]:
    import json

    user = (
        "## Current spec\n\n```json\n"
        + json.dumps(spec.model_dump(mode="json"), indent=2)
        + "\n```\n\n## The change the user asked for\n\n"
        + change.strip()
        + "\n"
    )
    return AMEND_SYSTEM, user
