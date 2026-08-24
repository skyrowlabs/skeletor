"""Spec + models + smoke tests -> app/routes.py.

This pass is handed the generated tests as its target. That is the payoff for
generating them first: the routes pass is not asked to guess a URL scheme, it
is asked to satisfy assertions that already exist.
"""

from __future__ import annotations

from protogen import baseline
from protogen.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "routes"
WRITES = ("app/routes.py",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write `app/routes.py` -- and only that file. It exports `router`, an
`APIRouter`.

You are given `tests/test_smoke.py`, which already exists and will be run
against your output. Satisfying it is the job. If a test expects a path, that
path exists; if it expects a 404, raise `HTTPException(status_code=404, ...)`.

Per entity: list, new-form (GET), create (POST), detail, edit-form (GET),
update (POST) and delete (POST). Plus `GET /` for the home screen.

- Every handler takes `db: Session = Depends(get_db)`, and every HTML handler
  takes `request: Request` and returns
  `templates.TemplateResponse(request, "<name>.html", {...})` -- the newer
  signature with `request` first.
- POST handlers are `async def` and read `form = await request.form()`.
  Coerce every value with the `app.forms` helpers; a required column gets a
  fallback so an empty submit is a form the user can fix rather than a 500
  from the database.
- POST handlers end with
  `RedirectResponse(url, status_code=303)`. 303 specifically: the default 307
  replays the POST on the redirect target and double-creates the row.
- Look rows up with `db.get(Model, row_id)` and 404 on `None`. Query lists
  with `db.scalars(select(Model).order_by(Model.id)).all()`.
- A form screen for an entity with a parent must pass the candidate parents
  into the template so the user can pick one.
- Declare path params as typed function arguments (`row_id: int`), never by
  parsing the path yourself.

Name templates `<plural>_list.html`, `<plural>_detail.html`,
`<plural>_form.html`, plus `index.html`. The UI pass generates exactly those
names from the same rule, so a name invented here is a 500 at render time.
"""


def build(spec, ctx) -> tuple[str, str]:
    user = (
        spec_block(spec)
        + "\n\n## Already generated\n\n"
        + ctx.sources("app/models.py", "tests/test_smoke.py")
    )
    return STACK_BRIEF + TASK, user


def offline(spec, ctx) -> dict:
    return {
        "files": [{"path": "app/routes.py", "content": baseline.routes_py(spec)}],
        "notes": "baseline: seven CRUD routes per entity plus an index.",
    }
