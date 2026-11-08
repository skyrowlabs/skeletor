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

That was fixed where it could be: this block, the README's and `AGENTS.md`'s were
generated from one source when this repository was scaffolded. **Do not read that
as a standing guarantee** — a guarantee implemented by rendering is spent at the
moment of rendering. All three are static text here, the generator is not present,
and the three files wrap the shared steps differently.

What holds them together now is `tests/test_setup_blocks_agree.py`, which ratchets
on how many leading lines the three blocks agree on and fails when that number
drops. Change a shared step and you change it in all three, by hand — and the test
tells you if you missed one.

That last sentence is a present-tense claim about a mechanism, which is exactly
what the paragraph above says to distrust. It is honest here for the single reason
the warning turns on: the test ships beside this file and runs in the same
`{{CLI}} check pre-push`, so there is no rendering step between the claim and its
enforcement, and nothing that could separate them later.

Two things it installs are easy to miss, because they live outside version control:

- **Git hooks** (`pre-commit install --install-hooks`, above) — the commit-msg
  format check and the lint gates.
- **The clone-local config** (`scripts/git/install_merge_drivers.py`, on the same
  line) — the `regen-docs` merge driver and `commit.template`. Both live in
  `.git/config`, which is not tracked, so a clone that skipped that line has
  `.gitattributes` naming a driver that does not exist and a `check pre-push` that
  is red until it runs. Verify with `{{CLI}} check merge-drivers`, which checks and
  never installs.
- **The pre-push hook** (`scripts/hooks/pre-push`, installed by that same script) —
  see [Pushing](#pushing). Git runs a copy under `.git/hooks`, so a changed hook needs
  the installer again, and `check pre-push` is red until it has run.

## Pushing

A push to `{{BASE_BRANCH}}` or `{{RELEASE_BRANCH}}` needs evidence that the pushed tree was
checked. Commit first, then run the gates, then push:

```bash
./{{CLI}} check pre-push
git push
```

A full run on a checkout with nothing uncommitted stamps `HEAD^{tree}` under the git
common dir. The hook reads every ref in the push, and a protected one passes if the
pushed commit's tree is stamped or equals the fetched tip of either branch, which CI has
already seen. Otherwise it refuses and names the command. Other branches, tags and
deletes are not judged.

- **The stamp is per tree.** Rewording a commit keeps it. A merge or a pull that
  produces a new tree needs a fresh run, so every direct push pays for a full
  `check pre-push`.
- **`--quick` never stamps,** and a run with uncommitted changes says it did not.
- **`git push --no-verify` skips the hook.** Nothing records that it did.
- **An unattended job pushing to a protected branch is refused** until it runs the gates
  first.
- **The installer leaves a pre-push hook it did not write alone,** and `check pre-push`
  stays red until you remove it. To decline the hook, delete `scripts/hooks/pre-push` and
  `tests/test_green_stamp.py`.

## Configuration

Every value the application reads appears in `.env.example` with a comment. The
real `.env` is untracked, and a pre-commit hook refuses any `.env*` that is not
the example — a committed secret is a rotated secret.

Read config through the validated config object, never `os.getenv()` at the
point of use. Validation happens once at startup, so a misconfigured process
refuses to boot rather than failing on the first request that needs the value.

## The Gates

Every gate CI blocks on is runnable locally with the same invocation, **except
the integration suite**, which needs the stack up and so has no host equivalent.
That one exception is declared in `tests/test_pre_push_covers_ci.py`, which fails
when CI grows a blocking gate `pre-push` neither runs nor declares — the earlier
version of this sentence said "everything" and was wrong about three gates.

```bash
./{{CLI}} check pre-push        # every host-runnable one, in fail-fastest order
./{{CLI}} check pre-push --quick # no test suites; the rest still run
./{{CLI}} check lint            # the blocking lint set
./{{CLI}} check docs            # indexes, tables, links, refs, report anchors
```

Every gate runs even after one fails. One fix per round trip is the thing this
exists to avoid.

Your own gates go in `scripts/gates.py`, as an append to `DOCS_GATES` (run by
`check docs` and `check pre-push`) or `PRE_PUSH_GATES` (`check pre-push` alone).
Editing a list in `{{SHELL_PACKAGE}}/check.py` instead conflicts with every
release that adds a gate there.

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
./{{CLI}} test coverage --suite unit --suite ui   # only these suites, budgeted as unit+ui
```

`--ci` sets `{{CI_ENV_VAR}}=1`, under which an env-gate skip becomes a **failure**.
That is the difference between "the suite passed" and "the suite ran".

Full rules: [`docs/rules/testing.md`](rules/testing.md).

## CI/CD Pipeline

| Event                          | What runs                              | ~min |
| ------------------------------ | -------------------------------------- | ---- |
| Draft PR, docs-only            | `CI Gate` + `pytest`                   | ~4   |
| Draft PR carrying code         | `CI Gate` + `Node` + `pytest`          | ~5   |
<!-- SCAFFOLD-IF-DIFFER {{BASE_BRANCH}} {{RELEASE_BRANCH}} -->
| Ready PR → `{{BASE_BRANCH}}`, docs-only | `CI Gate` + `pytest`          | ~4   |
| Ready PR → `{{BASE_BRANCH}}`, code      | `CI Gate` + `Node` + `pytest` | ~5   |
| Ready PR → `{{RELEASE_BRANCH}}`, docs-only | `CI Gate` + `pytest`       | ~4   |
| Ready PR → `{{RELEASE_BRANCH}}`, code      | **everything**             | full |
<!-- /SCAFFOLD-IF -->
<!-- SCAFFOLD-IF-SAME {{BASE_BRANCH}} {{RELEASE_BRANCH}} -->
| Ready PR, docs-only            | `CI Gate` + `pytest`                   | ~4   |
| Ready PR carrying code         | **everything**                         | full |
<!-- /SCAFFOLD-IF -->
| Ready PR opened by Dependabot  | **everything** — deliberately exempt   | full |
<!-- SCAFFOLD-IF .github/release-please-config.json -->
| Push to {{PROTECTED_BRANCHES}} | **everything**, and Release Please on `{{RELEASE_BRANCH}}` | full |
<!-- /SCAFFOLD-IF -->
<!-- SCAFFOLD-IF-NOT .github/release-please-config.json -->
| Push to {{PROTECTED_BRANCHES}} | **everything**                         | full |
<!-- /SCAFFOLD-IF -->

Three things about this table are load-bearing:

1. **A required context that reports `skipped` satisfies branch protection** —
   under its real name. So gating is done with `if:` on the job, never
   `paths-ignore` on the trigger: a required check that never reports at all
   blocks the PR forever.

   **The unit suite is never gated, docs-only included**, because its tests
   read `docs/` — plans, tables, references — so a docs-only change is what
   they judge. It runs once per interpreter, as `pytest <version>`, and a
   skipped matrix reports one check with the expression unexpanded, so a
   protection requiring `pytest <version>` can wait forever.
   **Require `pytest`, never `pytest <version>`.** `pytest` is one job that
   `needs:` the matrix and always reports — pass when every leg passed, fail
   otherwise, including when the gate failed and nothing ran. A protection
   set up before that job existed names the per-version contexts; no file in
   this tree can change that setting, so check it.

   **Change it one branch at a time, and only once that branch carries the
   job.** A pull request runs the `ci.yml` of its merge commit, so a required
   context reaches it only if the base or the head has the job that reports it.
   Require `pytest` on a branch whose `ci.yml` predates it and every pull request
   into that branch from a branch cut from it — a hotfix, typically — waits
   forever on a check nothing will run. The release branch is the one that
   lags: it gets the job only when the base branch is next merged into it.
2. **Requiring a context costs nothing; only running a job does.** Size the
   required list for what must gate. Never trim it to save minutes.
3. **The Dependabot exemption is a mechanism, not a courtesy.** Auto-merge fires
   the moment branch protection is satisfied, so without the exemption every
   eligible bump merges having never run the suite it exists to be checked by.

### Dependency updates

`.github/dependabot.yml` proposes version updates monthly, each held back five
days (`cooldown`) so a hijacked release can be yanked before it is proposed.
`.github/workflows/dependabot-auto-merge.yml` merges a Dependabot pull request
once CI passes on it, using the GitHub App's token (`APP_ID`, `APP_PRIVATE_KEY`)
so the merge itself runs CI on the base branch. Patches and minors merge,
security updates included, and so does a major in a dev manifest
(`scripts/requirements.txt`, `requirements-dev*.txt`, `package.json`
devDependencies), because the suite running under it is the migration test. A
major anywhere else is runtime and is left for a person. The decision, and the
list of dev manifests to extend, is `.github/scripts/dependabot-hold.cjs`. Without the App's secrets it merges
nothing and says so in the run.

The lint tools (black, flake8, isort, pyright) are ignored there. Each is pinned
in two files and `tests/test_lint_tool_parity.py` is red until both agree, so a
bump to one of them could never merge. Bump those by hand, in both files.

## Releases

<!-- SCAFFOLD-IF .github/release-please-config.json -->
Versioning is Conventional Commits → Release Please. Commit types decide the
bump; `CHANGELOG.md` and `VERSION` are generated. **Never hand-edit either.**

**Known: a pull request merged with a merge commit lists its change twice.**
GitHub writes the PR title into the merge commit's body by default, and Release
Please reads that line as a second commit (sky.vault, sky.boss and proto.pilot,
each at its first releases). The template leaves merge settings to you: squash
merges, or PR titles with a hidden type such as `chore:`, avoid it.
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
<!-- SCAFFOLD-IF-DIFFER {{BASE_BRANCH}} {{RELEASE_BRANCH}} -->

The release lands on `{{RELEASE_BRANCH}}`, so back-merge it. Until you do,
`{{BASE_BRANCH}}` does not contain the release commit, and `git describe` there
names the release before this one (mind.head):

```bash
git fetch origin && git switch {{BASE_BRANCH}} && git merge --ff-only origin/{{RELEASE_BRANCH}} && git push
```

A fast-forward, because a merge commit is a commit no check has run on, and a
`{{BASE_BRANCH}}` with required checks takes it only by admin bypass (sky.vault).
After a promote `{{BASE_BRANCH}}` is normally an ancestor of `{{RELEASE_BRANCH}}`,
so the fast-forward gives the same tree. If git refuses, `{{BASE_BRANCH}}` has moved
since: open the back-merge as a pull request from `{{RELEASE_BRANCH}}` and merge it
with a merge commit, so it runs the checks and keeps the release commit an ancestor.
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

### After an upgrade

An upgrade that writes leaves `tmp/upgrade/REPORT.md` behind: the conflict
count, the base it started from and each pending file are filled in, and every
other section says in a comment what belongs there. Fill those in, whoever ran
it, so every upgrade of this tree is reported the same way. A second run of the
same upgrade, such as `--ported`, keeps what you wrote and marks a conflict you
resolved; an upgrade to a different version starts the file again.

### A scheduled workflow

No pull request runs a job triggered by `schedule:`, so its first real run is
the night after the merge. Run it here first:

```bash
./{{CLI}} check scheduled --plan   # what would run, and where it would stop
./{{CLI}} check scheduled          # run it: the working tree, a clean venv
```

It rehearses the working tree as `git add -A` would commit it, so run it straight
after an upgrade, before committing. It exits 3, no subject, when no job could be
rehearsed in full: nothing was checked, and it still names where each job stopped.

A clean venv is the point. A dependency only that job needs is missing there
and present in your `.venv`, so the rehearsal fails and your own suite passes.
What it cannot stand in for (another action, a secret, a condition beyond
`github.event_name`) stops the job, and the job is reported as not rehearsed,
never as passing. `scripts/rehearse_scheduled.py` has the rules.
