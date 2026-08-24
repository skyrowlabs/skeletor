"""Orchestration: run the passes, then drive the tree to green.

The pass order is the design, not an accident:

    schema -> smoke -> seed -> routes -> ui

Tests come second, before any of the code they test, so they describe what was
asked for rather than what got built; the routes pass is then handed them as
its target. UI comes last because it is the pass most dependent on real
source -- a template referencing a context key no route passes is the single
most common way a generated app 500s.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from protogen.llm import LLM
from protogen.passes import PassContext, PassResult, repair, routes, seed, smoke, ui
from protogen.passes import models as schema_pass
from protogen.passes import run_pass
from protogen.spec import Spec
from protogen.verify import VerifyResult, Verifier

CODE_PASSES = (schema_pass, smoke, seed, routes, ui)
SMOKE_PATH = "tests/test_smoke.py"

Log = Callable[[str], None]


@dataclass
class Outcome:
    ok: bool
    attempts: int
    result: VerifyResult | None
    history: list[VerifyResult] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)


def generate(spec: Spec, ctx: PassContext, llm: LLM, log: Log = print) -> list[PassResult]:
    results = []
    for module in CODE_PASSES:
        log(f"  pass {module.NAME}...")
        result = run_pass(module, spec, ctx, llm)
        log(f"    {len(result.files)} file(s): {', '.join(str(f) for f in result.files)}")
        results.append(result)
    return results


def _test_count(project_dir: Path) -> int:
    path = project_dir / SMOKE_PATH
    return len(re.findall(r"^def test_", path.read_text(), re.M)) if path.exists() else 0


def drive_to_green(
    spec: Spec,
    ctx: PassContext,
    llm: LLM,
    verifier: Verifier,
    attempts: int = 3,
    log: Log = print,
) -> Outcome:
    """Verify, and on failure repair and verify again, up to `attempts` times.

    The loop is bounded and has a floor. Three attempts is not a tuned number;
    it is the point past which the failures observed stop being typos and
    start being the model disagreeing with itself, which more attempts do not
    fix. Past it the tree is handed back with a RUNBOOK rather than silently
    failing -- a prototype whose broken shape you know beats a mystery.
    """
    history: list[VerifyResult] = []
    repairs: list[str] = []

    for attempt in range(1, attempts + 2):
        log(f"  verify (attempt {attempt})...")
        result = verifier.verify()
        history.append(result)
        if result.ok:
            log(f"    {result.summary}")
            return Outcome(True, attempt, result, history, repairs)

        log(f"    failed at {result.stage}: {result.summary}")
        if attempt > attempts:
            break

        before = _test_count(ctx.project_dir)
        original = (ctx.project_dir / SMOKE_PATH).read_text() if before else ""

        ctx.failure = result.report()
        log("  pass repair...")
        try:
            patch = run_pass(repair, spec, ctx, llm)
        except Exception as exc:  # noqa: BLE001 -- a failed repair is an outcome
            log(f"    repair pass failed: {exc}")
            break
        if not patch.files:
            log(f"    repair produced no changes: {patch.notes}")
            break
        log(f"    patched {', '.join(str(f) for f in patch.files)}")
        repairs.append(f"attempt {attempt} ({result.stage}): {patch.notes}")

        # A repair is not allowed to make the suite pass by shrinking it.
        # This is the one guardrail the prompt alone cannot enforce, and the
        # failure mode it prevents -- green because there is nothing left to
        # fail -- is the only one that would go unnoticed.
        after = _test_count(ctx.project_dir)
        if before and after < before:
            (ctx.project_dir / SMOKE_PATH).write_text(original)
            log(
                f"    rejected: repair cut the smoke suite from {before} to "
                f"{after} tests; reverted {SMOKE_PATH}"
            )
            repairs[-1] += "  [test deletion rejected and reverted]"

    return Outcome(False, len(history), history[-1] if history else None, history, repairs)


RUNBOOK = """\
# Runbook

protogen could not get this prototype to green in {attempts} attempt(s), so it
handed the tree over as it stands rather than failing silently. Everything
below is what it knows.

## Where it stops

Stage: **{stage}**

{summary}

## Last output

```
{output}
```

## Container logs

```
{logs}
```

## What was tried

{repairs}

## Carrying on by hand

```bash
docker compose up -d --build        # bring it up
docker compose logs -f app          # watch it
docker compose exec -T app pytest -q   # the failing suite
```

Generated files -- rewritten whole by the next `proto add`, so fix them here
only if you are done generating:

{generated}

The rest of the tree is the fixed protogen skeleton and is very unlikely to be
the problem.
"""


def write_runbook(project_dir: Path, spec: Spec, outcome: Outcome) -> Path:
    result = outcome.result
    generated = "\n".join(
        f"- `{p}`"
        for p in ["app/models.py", "app/seed.py", "app/routes.py", SMOKE_PATH]
        + sorted(
            f"app/templates/{q.name}"
            for q in (project_dir / "app" / "templates").glob("*.html")
            if q.name != "base.html"
        )
    )
    repairs = (
        "\n".join(f"{i}. {r}" for i, r in enumerate(outcome.repairs, 1))
        or "Nothing -- the first verify failed and no repair was attempted."
    )
    path = project_dir / "RUNBOOK.md"
    path.write_text(
        RUNBOOK.format(
            attempts=outcome.attempts,
            stage=result.stage if result else "unknown",
            summary=result.summary if result else "no verify result was produced",
            output=(result.output if result else "").strip()[-4000:] or "(none)",
            logs=(result.logs if result else "").strip()[-4000:] or "(none)",
            repairs=repairs,
            generated=generated,
        )
    )
    return path
