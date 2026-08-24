"""A failing verify run -> patched files.

The repair pass is handed the stage that failed, the command output, the
container logs, and the full current source of every generated file. Logs
matter as much as the test output: the boring 80% of first-run failures are a
missing import, a template name that does not exist, or a column the seed
references and the model does not have -- and all three say so in the log and
say nothing useful in the assertion.
"""

from __future__ import annotations

from protogen.files import WRITABLE
from protogen.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "repair"
WRITES = WRITABLE
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

The generated application does not work. You are given the stage that failed,
the output, the container logs, and the current contents of every generated
file. Fix it.

Return the COMPLETE contents of only the files you are changing. A file you do
not return is left alone -- do not return files you have not edited.

- Diagnose from the logs and the traceback, not from what the code looks like
  it should do. The failure has a specific cause; name it to yourself before
  you change anything.
- Make the SMALLEST change that fixes the cause. Do not refactor, do not
  rename, do not "also improve" something on the way past. A repair that
  rewrites a working file turns one red test into two.
- Never make a test pass by deleting it, weakening its assertion, or wrapping
  it in a skip. If a test genuinely contradicts the spec, say so in `notes`
  and fix the test to match the spec -- never to match the code.
- Common causes, in the order they actually occur: a template referencing a
  context key its route does not pass; a template filename the route does not
  match; a column name that differs between models, seed and routes; a
  redirect with the default 307 instead of 303; a missing import; a required
  column receiving None from an empty form field.
"""


def build(spec, ctx) -> tuple[str, str]:
    sources = ctx.sources(
        "app/models.py",
        "app/seed.py",
        "app/routes.py",
        "tests/test_smoke.py",
        *ctx.template_files(),
    )
    user = (
        "## What went wrong\n\n```\n"
        + ctx.failure.strip()
        + "\n```\n\n"
        + spec_block(spec)
        + "\n\n## Current source of every generated file\n\n"
        + sources
    )
    return STACK_BRIEF + TASK, user


def offline(spec, ctx) -> dict:
    # The baseline generator has no diagnostic faculty. Saying so lets the
    # loop stop cleanly and write a runbook rather than spin.
    return {
        "files": [],
        "notes": "offline mode cannot repair; re-run without --offline to fix this.",
    }
