# Development Guide

## First-Time Setup

```bash
{{SETUP_COMMANDS}}
cp .env.example .env
./{{CLI}} check pre-push   # green on a fresh tree
```

**There is no `{{CLI}} setup`, and there cannot be.** The CLI needs `click`, which
lives in the virtualenv the setup would be creating — so a `setup` subcommand
could not run until after the work it exists to do. This section opened with one
anyway, for long enough that it shipped: the developer guide's very first command
did not exist, in a repository whose `AGENTS.md` explained on the same page that it
never had. Nothing could see the disagreement, because the two files were separate
copies of one instruction.

That was fixed where it could be: the block above and the README's were generated
from one source when this repository was scaffolded. **Do not read that as a
standing guarantee** — a guarantee implemented by rendering is spent at the moment
of rendering. Both blocks are static text here, the generator is not present, and
the two files wrap the shared steps differently. Change the setup steps and you
change them in both places, by hand, and nothing will tell you if you miss one.

Two things it installs are easy to miss, because they live outside version control:

- **Git hooks** (`pre-commit install --install-hooks`, above) — the commit-msg
  format check and the lint gates.
- **The `regen-docs` merge driver** — its definition lives in `.git/config`, which
  is not tracked, so a fresh clone has `.gitattributes` pointing at a driver that
  does not exist. **Every clone after the first installs it by hand:**
  `python scripts/git/install_merge_drivers.py`. Verify with
  `{{CLI}} check merge-drivers`, which checks and never installs.

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

Full rules: [`docs/rules/testing.md`](rules/testing.md).

## CI/CD Pipeline

| Event                          | What runs                              | ~min |
| ------------------------------ | -------------------------------------- | ---- |
| Draft PR                       | `CI Gate` alone                        | ~1   |
| Ready PR → `{{BASE_BRANCH}}`, docs-only | `CI Gate` alone               | ~1   |
| Ready PR → `{{BASE_BRANCH}}`, code      | `CI Gate` + `Unit Tests`      | ~5   |
| Ready PR opened by Dependabot  | **everything** — deliberately exempt   | full |
<!-- SCAFFOLD-IF .github/release-please-config.json -->
| Push to `{{RELEASE_BRANCH}}`   | **everything** + Release Please        | full |
<!-- /SCAFFOLD-IF -->
<!-- SCAFFOLD-IF-NOT .github/release-please-config.json -->
| Push to `{{RELEASE_BRANCH}}`   | **everything**                         | full |
<!-- /SCAFFOLD-IF -->

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

<!-- SCAFFOLD-IF .github/release-please-config.json -->
Versioning is Conventional Commits → Release Please. Commit types decide the
bump; `CHANGELOG.md` and `VERSION` are generated. **Never hand-edit either.**
<!-- /SCAFFOLD-IF -->
<!-- SCAFFOLD-IF-NOT .github/release-please-config.json -->
Versioning is the annotated git tag and nothing else. There is no `VERSION`
file and no `CHANGELOG.md`: a repository run from a checkout already has the
answer in `git describe`, and a file would be a second home for it — kept in
step by hand, wrong the first time somebody forgets.

Cut a release with `git tag -a vX.Y.Z -m "what moved"` and **push the tag** — an
unpushed tag names a version only your machine can resolve, and `{{CLI}} --version`
reads exactly this. Conventional commit subjects are still the rule; they are
what a reader of `git log` between two tags gets instead of a changelog.
<!-- /SCAFFOLD-IF -->

A release closes the report window: in-flight reports under
`docs/reports/regular/` freeze into `docs/reports/releases/<tag>/`. See
[`docs/rules/docs.md`](rules/docs.md).

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
Full rules: [`docs/rules/output.md`](rules/output.md).

## Reproducing a CI Failure Locally

```bash
./{{CLI}} check lint                        # 1. fastest feedback; catches most CI rejections
./{{CLI}} test unit --ci                    # 2. CI's skip semantics
{{CLI_ENV_PREFIX}}_PYTHON=.venv-ci/bin/python ./{{CLI}} check pre-push   # 3. CI's exact interpreter
```

Step 3 matters more than it looks. A local venv that has drifted from CI's
pinned interpreter produces failures that exist in one environment and not the
other, and the tool names are identical, so the version never occurs to anyone.
