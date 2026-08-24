# Testing Rules

Applies to everything under `tests/`.

## Registration Is Marker-Based — No Registries

A test file registers itself **by existing**. Declare which environment runs it with a
module-wide `pytestmark`:

```python
import pytest

pytestmark = [pytest.mark.unit]   # see tests/pytest.ini for the full marker list
```

| Marker        | Environment                                  | Run with                 |
| ------------- | -------------------------------------------- | ------------------------ |
| `unit`        | Host, no services required                   | `{{CLI}} test unit`        |
| `integration` | Services up, seeded data                     | `{{CLI}} test integration` |
| `manual`      | Never in scheduled CI (E2E, live third-party, paid APIs) | `{{CLI}} test manual` |

`tests/test_marker_coverage.py` fails the unit suite if a test file declares no marker.

**Never** add a per-feature CI step, a `run_tests.sh` case, or a CLI entry for a new test
file. Those are registries, and *forgetting to update a registry is the same bug* the marker
exists to remove. Dual-environment files list multiple markers.

## Behavioral Assertions Only

- ❌ No source-grep asserts (`assert "csrf" in open(...).read()`) — test the behaviour.
- ❌ No assert-only-`isinstance` / `is not None` — assert values, shapes, side effects,
  status codes.
- ❌ Never mock the method under test. Mock only true externals at the boundary.
- ✅ Cover the happy path, the edge cases, **and** the error cases.
- ✅ Prefer real local infrastructure (a test database, a fake in-process cache) over mocking
  storage — a mocked store cannot fail the way a real one does.

A test that `return`s instead of asserting cannot fail: pytest discards the value.
`filterwarnings = error::pytest.PytestReturnNotNoneWarning` in `tests/pytest.ini` makes that
an error on our schedule rather than during a future version bump.

## Env-Gate Skips: `require_or_skip`, Not `pytest.skip`

```python
from conftest import require_or_skip

require_or_skip(services_up, "the app is not reachable", requires="services")
```

Locally it **skips**; under `{{CI_ENV_VAR}}=1` it **fails**. CI guarantees the services, so a skip
there means the harness broke, and a harness that silently skips its whole suite reports
green. Raw `pytest.skip` is only for genuine cross-environment conditions CI does not
guarantee.

## Never Create State Without a Teardown

Every fixture that creates a record owns its deletion. A cleanup that runs at *startup* is
not a teardown — it hides the leak for exactly as long as it takes to become someone else's
problem. Use the fixtures in `tests/fixtures.py`; never construct records against a live
session by hand.

## Budgets Are Ratchets — Update Them in the Same Commit

Two counts are pinned so they can only move deliberately:

- **Skips**: `scripts/check_skip_budget.py` against `tests/skip_budget.json`.
- **Coverage**: `scripts/check_coverage_budget.py` against `tests/coverage_budget.json`.

Adding a legitimate skip → raise the budget **in the same commit** and justify it in the
body. Removing skips, or raising coverage meaningfully → lower/raise the baseline in the same
commit to lock the gain in. A ratchet is not a target: never chase the number.

## Before You Commit

```bash
{{CLI}} test unit            # the fast suite — must be green
{{CLI}} check pre-push       # everything CI runs, locally
```

All tests must pass. Never commit half-working code.
