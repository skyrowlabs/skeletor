"""Spec + models -> tests/test_smoke.py.

Deliberately generated BEFORE routes, templates and seed data. Tests written
after the code describe whatever the code happened to do; these describe what
was asked for, so a route the model forgot is a red test rather than a silent
omission. The routes pass is then handed these tests as its target.
"""

from __future__ import annotations

from protogen import baseline
from protogen.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "smoke"
WRITES = ("tests/test_smoke.py",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write `tests/test_smoke.py` -- and only that file.

The routes and templates DO NOT EXIST YET. You are writing the target they
will be generated against. Test what the spec promises, not what you imagine
the implementation will look like.

`tests/conftest.py` already provides two fixtures:

- `client`: a `fastapi.testclient.TestClient` bound to the real app, with
  lifespan run (so tables exist and seed data is loaded).
- `db`: a fresh `Session`. It is a DIFFERENT session from the app's, so after
  a request that writes, call `db.rollback()` before re-querying -- otherwise
  the open transaction hides the row the app just committed.

Cover, per entity:

- the list screen returns 200
- the "new" form screen returns 200
- seed data exists (`count > 0`) -- a prototype with empty tables cannot be
  demonstrated
- the detail screen for a seeded row returns 200 (look the row up through
  `db` first; never hard-code an id)
- an unknown id on the detail screen returns 404
- a create round trip: POST the form, follow redirects, expect 200, then
  assert the row count went up by exactly one

Plus one test that `GET /` returns 200.

Rules: pytest functions, no classes, no fixtures of your own, no mocking. Put
`response.text` in every status assertion's message -- when this fails inside
a container it is the only traceback anybody gets. Assert on status codes and
row counts, not on page copy: an assertion about wording makes the UI pass
fail for choosing a different verb.
"""


def build(spec, ctx) -> tuple[str, str]:
    user = spec_block(spec) + "\n\n## Already generated\n\n" + ctx.sources("app/models.py")
    return STACK_BRIEF + TASK, user


def offline(spec, ctx) -> dict:
    return {
        "files": [{"path": "tests/test_smoke.py", "content": baseline.smoke_py(spec)}],
        "notes": "baseline: list, form, seed, detail, 404 and create round trip per entity.",
    }
