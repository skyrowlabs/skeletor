# Development Guide

## First-Time Setup

```bash
./{{CLI}} setup          # .env from .env.example, git hooks, merge drivers
./{{CLI}} check health   # is everything answering?
```

`{{CLI}} setup` installs two things that are easy to miss because they live outside
version control:

- **Git hooks** (`pre-commit install --install-hooks`) — the commit-msg format
  check and the lint gates.
- **The `regen-docs` merge driver** — its definition lives in `.git/config`,
  which is not tracked, so a fresh clone has `.gitattributes` pointing at a
  driver that does not exist. Verify with `{{CLI}} check merge-drivers`.

## Configuration

Every value the application reads appears in `.env.example` with a comment. The
real `.env` is untracked, and a pre-commit hook refuses any `.env*` that is not
the example — a committed secret is a rotated secret.

Read config through the validated config object, never `os.getenv()` at the
point of use. Validation happens once at startup, so a misconfigured process
refuses to boot rather than failing on the first request that needs the value.

## The Gates

Everything CI blocks on is runnable locally, with the same invocation:

```bash
./{{CLI}} check pre-push        # all of it, in fail-fastest order
./{{CLI}} check pre-push --quick # lint + docs only, no test suites
./{{CLI}} check lint            # the blocking lint set
./{{CLI}} check docs            # indexes, tables, links, refs, report anchors
```

Every gate runs even after one fails. One fix per round trip is the thing this
exists to avoid.

## Testing

Suites are selected by **marker**, and a test file joins a suite by declaring
one. There is no registry to update:

```python
pytestmark = [pytest.mark.unit]
```

```bash
./{{CLI}} test unit             # host-side, no services
./{{CLI}} test integration      # needs the stack up
./{{CLI}} test all              # everything except `manual`
./{{CLI}} test unit --ci        # reproduce CI's skip semantics locally
./{{CLI}} test coverage -w 20   # the worst-covered modules — where a test buys most
```

`--ci` sets `{{CI_ENV_VAR}}=1`, under which an env-gate skip becomes a **failure**.
That is the difference between "the suite passed" and "the suite ran".

Full rules: [`.claude/rules/testing.md`](../.claude/rules/testing.md).

## CI/CD Pipeline

| Event                          | What runs                              | ~min |
| ------------------------------ | -------------------------------------- | ---- |
| Draft PR                       | `CI Gate` alone                        | ~1   |
| Ready PR → `{{BASE_BRANCH}}`, docs-only | `CI Gate` alone               | ~1   |
| Ready PR → `{{BASE_BRANCH}}`, code      | `CI Gate` + `Unit Tests`      | ~5   |
| Ready PR opened by Dependabot  | **everything** — deliberately exempt   | full |
| Push to `{{RELEASE_BRANCH}}`   | **everything** + Release Please        | full |

Three things about this table are load-bearing:

1. **A required context that reports `skipped` satisfies branch protection.**
   So gating is done with `if:` on the job, never `paths-ignore` on the trigger
   — a required check that never reports at all blocks the PR forever.
2. **Requiring a context costs nothing; only running a job does.** Size the
   required list for what must gate. Never trim it to save minutes.
3. **The Dependabot exemption is a mechanism, not a courtesy.** Auto-merge fires
   the moment branch protection is satisfied, so without the exemption every
   eligible bump merges having never run the suite it exists to be checked by.

## Releases

Versioning is Conventional Commits → Release Please. Commit types decide the
bump; `CHANGELOG.md` and `VERSION` are generated. **Never hand-edit either.**

A release closes the report window: in-flight reports under
`docs/reports/regular/` freeze into `docs/reports/releases/<tag>/`. See
[`.claude/rules/docs.md`](../.claude/rules/docs.md).

## Command Output

Every command splits its output the same way: **stdout is what a caller
consumes** (a `--json` payload, a generated block, a listing you may pipe) and
**stderr is what only a human reads** (status lines, progress, and the "what to
do next" under an error).

Both land on your terminal, so an interactive run looks the same either way. The
difference appears the moment you pipe one:

```bash
python scripts/check_doc_tables.py --json | jq        # payload only
./{{CLI}} check docs 2>/dev/null                        # silent: it is all narration
```

Every `scripts/check_*.py` supports `--json` and answers on **every** path,
including the ones that pass — a ratchet you can only read when it is red says
nothing about which way it has been moving.

Nothing spells a status symbol or picks a stream by hand; it all comes from
`scripts/output.py`, and `{{CLI}} check output` enforces that by pattern.
Full rules: [`.claude/rules/output.md`](../.claude/rules/output.md).

## Reproducing a CI Failure Locally

```bash
./{{CLI}} check lint                        # 1. fastest feedback; catches most CI rejections
./{{CLI}} test unit --ci                    # 2. CI's skip semantics
{{CLI_ENV_PREFIX}}_PYTHON=.venv-ci/bin/python ./{{CLI}} check pre-push   # 3. CI's exact interpreter
```

Step 3 matters more than it looks. A local venv that has drifted from CI's
pinned interpreter produces failures that exist in one environment and not the
other, and the tool names are identical, so the version never occurs to anyone.
