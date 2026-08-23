# {{PROJECT_NAME}}

{{TAGLINE}}

> **Before making changes**: load docs on-demand via `docs/README.md` or `.github/DOCS_INDEX.md`.
> Never load the whole tree — a typical task needs one or two documents.

---

## Quick Start

```bash
./{{CLI}} setup            # first-time setup (.env, git hooks, merge drivers)
./{{CLI}} service up       # start the stack
./{{CLI}} check health     # verify everything is up
./{{CLI}} test unit        # the fast suite
```

---

## Services

<!-- SCAFFOLD: replace with this project's real components. Delete the row template. -->

| Service | Stack | Port | Purpose |
| ------- | ----- | ---- | ------- |
|         |       |      |         |

---

## Critical Rules

Numbered so they can be cited in review and in commit bodies. Each one exists because
something went wrong without it — keep the reason attached when you edit one.

### 1. Read the Config From One Place

Never re-derive a value that already has an owner. Feature parameters, schedules, windows,
sort orders, and version numbers are each resolved by exactly one module, which every
consumer **imports**. Two copies of a rule drift within the week, and the copy that is wrong
is always the one being read.

### 2. Test Code Before Delivery

Execute and verify in the correct environment before handing off. "It should work" is not a
result. If the code runs in a container, run it in that container.

### 3. Lint Before Committing

Run the blocking set after any change — see `.claude/rules/{{LANG_RULES}}.md`. CI blocks on
all of it, and the type check is **whole-project**: one stale error anywhere blocks every
commit, not just commits near it.

### 4. Run Tests Before Committing

`./{{CLI}} test <suite>` — all tests must pass. Never commit half-working code. Test files
self-register via a module-wide `pytestmark` marker; there are no registries to update.
Full rules in `.claude/rules/testing.md`.

### 5. Keep the CLI in Sync

Adding or changing a script means updating the `cli/` package in the same commit. A script
nobody can discover is a script nobody runs.

### 6. Commit Strategy — Frequent, Logical, Bundled

One commit per logical idea, all of its files bundled into that commit. Conventional format,
one subject line. Full rules in `.claude/rules/commits.md`.

### 7. Commit Autonomously — Push When Complete

Commit freely as each logical unit lands (tests green, conventions followed) — **no need to
ask permission**. Once the requested work is fully complete and all checks pass, push the
branch autonomously. Don't push half-finished work mid-task. **Force-push is permitted on
your own unreviewed branch** — but never on `{{BASE_BRANCH}}` or `{{RELEASE_BRANCH}}`, and
never from an unattended agent.

**Base branch: `{{BASE_BRANCH}}`.** New branches are cut from it; every PR targets it.
Never commit directly to `{{RELEASE_BRANCH}}`.

### 8. Open Every PR as a Draft

`gh pr create --draft`. Mark it ready only when you believe it is green.

The expensive CI jobs are gated on draft status: a draft PR runs the cheap gate job alone.
Nothing is un-gated by this — GitHub blocks merging a draft regardless, and marking it ready
fires `ready_for_review`, which runs the full set before it can merge.

**Flip back to draft before pushing a fix** — `gh pr ready --undo <n>`. A `synchronize` event
on a *ready* PR re-runs everything that PR earns; iterating in draft pays once, when the work
is actually done.

### 9. Docs Are Part of the Change, Not a Follow-Up

Decide in planning which docs a change will invalidate, and update them in the same PR. A
plan that is finished **moves** from `docs/TODO/` to `docs/implementations/` — never copies.
Both indexes are generated; never hand-edit them. Full rules in `.claude/rules/docs.md`.

### 10. No Temp Files in the Project Root

Use tool-based file editing. If a scratch file is genuinely necessary it goes in `tmp/`
(gitignored).

### 11. Anything That Stands Up the Stack Stays in Sync

If two files describe the same environment — a dev compose file and a CI one, two workflows
that both boot the stack, a host script that mirrors a CI action — **a drift check owns that
pair**, and intended divergences are recorded in an allowlist with a written reason.

Do not hand-copy setup between them. Enrollment in the drift check is **automatic** (anything
matching the pattern is checked); it is deliberately not a registry, because forgetting to
update a registry is the same bug the check exists to catch.

### 12. Found an Unrelated Bug? Capture It — Don't Widen Your Scope

A bug you hit that is **not** what you were asked to work on goes to the capture command, not
into your current change and not into a sentence the user will lose when the session ends:

```bash
./{{CLI}} bug "<one-line summary>" \
    --finding "<path:line + what is wrong>" \
    --reproduce "<exact command; observed vs expected>" \
    --scope "<what is in, what is explicitly out>" \
    --acceptance "<assertions; the command that must pass>"
```

All four sections are required — a capture missing any of them is refused, because a capture
nobody can act on is a note, not a task. Mention what you captured in your response so the
user can kill it if they disagree.

### 13. One Voice, Two Streams

Nothing prints a status symbol or picks a stream by hand. Every emission goes
through `scripts/output.py`: `ok` / `fail` / `warn` / `skip` / `step` to **stderr**,
`line` / `emit` to **stdout**.

The split is what makes `--json` free — the payload has the stream to itself, so
a machine-readable flag is one extra emit rather than a second code path. Every
`scripts/check_*.py` supports `--json` and answers on every path, including the
ones that pass. `{{CLI}} check output` enrols every file under `cli/` and
`scripts/` by pattern; exceptions go in `scripts/output_allowlist.yaml` with a
reason. Full rules in `.claude/rules/output.md`.

---

## Documentation Reference

Load on-demand only. Full mapping in `.github/DOCS_INDEX.md`.

| Topic                      | Doc                              |
| -------------------------- | -------------------------------- |
| Architecture / design      | `docs/ARCHITECTURE.md`           |
| Dev setup / CI / testing   | `docs/DEVELOPMENT.md`            |
| CLI commands               | `docs/CLI.md`                    |
| Unfinished work (the tank) | `docs/TODO/README.md`            |
| Completed work (archive)   | `docs/implementations/README.md` |

<!-- SCAFFOLD: add a row per doc as it is written. `{{CLI}} check docs` fails on a
     doc registered in neither this table nor .github/DOCS_INDEX.md — an
     unregistered doc is one no agent will load, which is the same, from the
     agent's point of view, as a doc that does not exist. -->

---

## Commit Types

`feat` / `fix` / `perf` / `docs` / `refactor` / `chore` / `ci` / `test` / `build`

> `docs:` for `docs/**` changes only — never `feat:`. Release Please owns `CHANGELOG.md`.
