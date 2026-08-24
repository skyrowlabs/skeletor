"""Prompt material shared by every code-generating pass.

STACK_BRIEF is byte-identical across passes and across repair attempts on
purpose: it is the cached prefix. Interpolating anything per-pass into it
would invalidate the cache on every call and quietly triple the bill.
"""

from __future__ import annotations

STACK_BRIEF = """\
You are generating one slice of a prototype web application. The rest of the
application already exists and is fixed. Work within it exactly.

## The fixed skeleton (you cannot change any of this)

- FastAPI, server-rendered Jinja2 templates, SQLAlchemy 2.0 (typed
  `Mapped[...]` / `mapped_column`), PostgreSQL. Python 3.12.
- There is NO JavaScript build step, NO npm, and NO CDN. The container has no
  outbound network access. Plain HTML forms and full page loads only.
- There are NO migrations. `Base.metadata.create_all()` runs at startup and
  the database is a tmpfs that is recreated with the container.

Modules you import from, which already exist:

- `app.db`      -> `Base`, `get_db` (FastAPI dependency yielding a `Session`),
                   `SessionLocal`, `engine`.
- `app.templating` -> `templates`, a configured `Jinja2Templates`. The globals
                   `app_name` and `app_purpose` are already registered, so
                   templates use them without any route passing them in.
- `app.forms`   -> `parse_str`, `parse_int`, `parse_float`, `parse_bool`,
                   `parse_date`, `parse_datetime`. Every one takes the raw
                   form value and an optional fallback and never raises. Use
                   these for all form input; never call `int()` on a form
                   value directly.
- `app.models`  -> the generated model classes.

`app/main.py` creates the app, mounts `/static`, includes `router` from
`app.routes`, runs `Base.metadata.create_all()` and then `seed(db)` on
startup, and serves `/healthz`. You do not write any of it.

`app/templates/base.html` exists and is fixed. It defines blocks `title` and
`content`, includes `_nav.html`, and links `/static/app.css`. That stylesheet
already styles: `.card`, `.row`, `.muted`, `.empty`, `.button`,
`.button.secondary`, `table`/`th`/`td`, `form`/`label`/`input`/`textarea`/
`select`/`button`, `nav a`, `nav a.active`. Use those classes; do not write
new CSS and do not add `<style>` blocks.

## Hard rules

1. Return COMPLETE file contents. Never a diff, never an ellipsis, never
   "... rest unchanged". Each file you return replaces its predecessor whole.
2. Write ONLY the paths you are told you may write. A path outside that list
   is rejected and the pass fails.
3. Every model class has a `display` property returning a short human label;
   templates and links use `row.display`.
4. Code must be importable at module scope with no side effects beyond
   defining things.
5. This is a prototype. Prefer the obvious implementation. No caching layers,
   no abstract base classes, no dependency-injection frameworks, no premature
   pagination. Do not add auth unless the spec asks for it.
"""

FILES_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative path, e.g. app/models.py",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file contents.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
        "notes": {
            "type": "string",
            "description": "One or two sentences on anything a later pass must know.",
        },
    },
    "required": ["files", "notes"],
    "additionalProperties": False,
}


def spec_block(spec) -> str:
    """The spec, rendered for a prompt. Both the JSON and the human summary:
    the JSON is what later passes must agree with, the summary is what the
    model actually reads."""
    import json

    return (
        "## The spec\n\n```json\n"
        + json.dumps(spec.model_dump(mode="json"), indent=2)
        + "\n```\n\n"
        + spec.summary()
    )
