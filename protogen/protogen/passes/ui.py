"""Spec + models + routes -> the Jinja templates.

Last, and given the real route source, because the single most common failure
in a generated app is a template referencing a context key no route passes.
"""

from __future__ import annotations

from protogen import baseline
from protogen.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "ui"
WRITES = ("app/templates/*.html",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write the Jinja templates. You may write any file under `app/templates/`
EXCEPT `base.html`, which is fixed.

Generate exactly the templates `app/routes.py` renders -- read its
`TemplateResponse` calls and produce one file per distinct name. Also write
`_nav.html`, which `base.html` includes: a `<nav>` with one link per entity
list screen.

Every template starts `{% extends "base.html" %}` and fills the `title` and
`content` blocks. `app_name` and `app_purpose` are already globals; do not
expect a route to pass them.

Use ONLY context keys the corresponding route actually passes. This is the
single most common way a generated app 500s at render time -- read the route,
then write the template.

Shape:

- list: a heading, a "New <Entity>" button, a `<table>` with one column per
  spec field, and a link to the detail screen per row. When the list is empty,
  a `<p class="empty">` with a link to the create form -- not a blank page.
- detail: `row.display` as the heading, a `<dl>` of the fields, a link back to
  the parent if there is one, a list of children if there are any, and Edit /
  Delete controls. Delete is a `<form method="post">` with a button, never a
  link -- a crawler or a prefetch must not be able to delete a row.
- form: one `<label>` per field wrapping its input, with the input type
  matching the field type (`text`, `textarea`, `number`, `checkbox`, `date`,
  `datetime-local`). Prefill from `obj` when it is set and leave blank when it
  is `None`. Render `date`/`datetime` values through `.isoformat()`;
  `<input type="datetime-local">` rejects Python's default rendering. An
  entity with a parent gets a `<select>` of candidate parents.
- index: the app name, its purpose, and a `.card` per entity linking to its
  list with a count.

Use the stylesheet's existing classes. Do not write CSS, do not add
`<style>`, do not add JavaScript.
"""


def build(spec, ctx) -> tuple[str, str]:
    user = (
        spec_block(spec)
        + "\n\n## Already generated\n\n"
        + ctx.sources("app/models.py", "app/routes.py")
    )
    if spec.direction:
        user += f"\n\nThe user's direction for how this should look and feel: {spec.direction}"
    return STACK_BRIEF + TASK, user


def offline(spec, ctx) -> dict:
    files = [
        {"path": path, "content": body}
        for path, body in sorted(baseline.templates_for(spec).items())
    ]
    return {
        "files": files,
        "notes": "baseline: nav, index, and list/detail/form per entity.",
    }
