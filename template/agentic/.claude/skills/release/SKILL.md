---
name: release
description: Cut a release — drive the integration branch to a tagged release as a phased state machine across multiple turns. Preflight every gate locally, sweep docs and close the report window, open and babysit the release PR, stop for the human to merge, then freeze the reports and back-merge. Use when the user says "cut a release" or "ship it".
---

# /release — Release Train

Drives `{{BASE_BRANCH}}` → tagged release on `{{RELEASE_BRANCH}}`. It is a **state
machine across turns**, not one long run: each phase ends at a checkpoint you
report, and Phase D stops entirely for a human.

**It never merges the release PR itself.**

---

## Phase A — Preflight

Run every gate the release PR will run, locally, against the tree being shipped.

```bash
git fetch origin {{BASE_BRANCH}}
git status --porcelain           # must be clean — a dirty tree grades the wrong thing
git rev-parse HEAD origin/{{BASE_BRANCH}}   # must match
{{CLI}} check pre-push
```

**Refuse to proceed if HEAD is not `origin/{{BASE_BRANCH}}`.** A release gate run
against whatever branch the shared tree was sitting on reports a verdict about
the wrong code — and the error always flatters the branch being shipped, which
is the direction that ships something broken.

Report the gate table. Red → stop; name the gate and what is failing.

## Phase B — Docs and reports for the closing window

The window that is about to close is `<previous tag>..HEAD`. Get it from one
place:

```bash
{{CLI}} docs release-window
```

1. Spawn the documenter with `--mode=repository-report --release=<the new tag>`
   so each in-flight report's prose describes the closing window in the past
   tense.
2. `{{CLI}} docs index` — the tank and archive indexes must be current.
3. `{{CLI}} check docs` — links, refs, tables, anchors.
4. Commit as one `docs:` commit.

## Phase C — Open the release PR and babysit it

```bash
gh pr create --base {{RELEASE_BRANCH}} --head {{BASE_BRANCH}} \
  --title "release: <version>" --body "<the changelog Release Please will generate>"
```

A PR into the release branch runs **everything**. Watch it; fix what breaks; push
fixes to `{{BASE_BRANCH}}`. Report when every check is green.

## Phase D — STOP. The human merges.

Report that the PR is green and ready, with its number and URL. **Do not merge
it.** Admin enforcement is deliberately off on the release branch precisely so
this step is a human's.

Then watch for the tag Release Please publishes.

## Phase E — Close the window

Once the tag lands:

```bash
{{CLI}} docs freeze-release --tag <tag>   # archive editions, re-anchor regular/, rebuild the index
git switch {{BASE_BRANCH}} && git merge --no-ff {{RELEASE_BRANCH}}   # back-merge the release commit
```

Report: tag, what shipped, where the frozen editions went, and anything left
open.

---

## Rules

1. **One phase per turn.** Each ends at a checkpoint you report; the user
   decides whether to continue.
2. **Never merge the release PR.**
3. **Never hand-edit `CHANGELOG.md` or `VERSION`.** Release Please owns both.
4. **Never edit a frozen report edition.** Corrections go in an `## Errata`
   block on the current in-flight edition.
5. **A red gate stops the train.** Do not proceed "to see if CI agrees" — CI
   agreeing would only mean two runs of the same wrong thing.
