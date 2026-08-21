# Documentation Rules

Applies to all files under `docs/**`.

## Folder Structure

All documentation lives in `docs/`. **Never create docs in the project root** — the root is
for configuration, and a doc there is a doc no index knows about.

| Type                                   | Location                   |
| -------------------------------------- | -------------------------- |
| Unfinished / shelved / deferred plans  | `docs/TODO/`               |
| Completed plans (the archive)          | `docs/implementations/`    |
| Periodic reports (live / in-flight)    | `docs/reports/regular/`    |
| Frozen per-release report editions     | `docs/reports/releases/`   |
| One-time deep-dive reports             | `docs/reports/occasional/` |
| Research / feasibility                 | `docs/research/`           |
| Business planning                      | `docs/business-planning/`  |

## TODO vs Implementations — Two Halves of One Lifecycle

- **`docs/TODO/`** is the **holding tank**: every plan that is _not finished_ — shelved, in
  progress, planned, blocked, or a deferred follow-up. Indexed by `docs/TODO/README.md` and
  `docs/todo_index.json`.
- **`docs/implementations/`** holds **only completed** plans. Indexed by
  `docs/implementations/README.md` and `docs/implementation_index.json`.

A plan **moves** (`git mv`) from one to the other when it is done. Never copy — the tank must
not contain a file the archive also contains, or "what is left to do" stops being answerable.

Both READMEs and both JSON indexes are **auto-generated**. Never hand-edit them: edit the
plan's frontmatter or header and regenerate.

## Shelf-Status Taxonomy

Every `docs/TODO/*.md` plan carries a **shelf status** — the machine-readable reason it is
unfinished. It drives the grouping in `docs/TODO/README.md`.

| Status        | Meaning                                                                        |
| ------------- | ------------------------------------------------------------------------------ |
| `ready`       | All decisions made; the spec is complete and an agent can finish it end to end |
| `in-progress` | Actively being worked; partially shipped                                       |
| `in-review`   | Implemented and out for review; waiting on the owner before filing             |
| `planned`     | Not started; intended future work, may still have open design questions        |
| `blocked`     | Code complete or startable, but gated on an external prerequisite              |
| `shelved`     | Built but intentionally parked behind a flag — has an un-shelve plan           |
| `deferred`    | Follow-up backlog carved off a completed feature (usually `*-deferred.md`)     |

Set it with an explicit header line, which always beats the inferred value:

```
> **Shelf-Status**: blocked
```

**`ready` is a work queue, not a label.** Promoting a plan to `ready` _is_ the act of handing
it to an agent, so the section must contain only things an agent can finish without you. A
plan whose remaining work needs a human is **`blocked`**, however agent-doable the rest is.

## Blocked-On Gates — What Unblocks a Plan

`shelf_status` says a plan is waiting; it does not say **for what**. Every `shelved` /
`blocked` / `deferred` plan also carries a gate, so plans sharing one can be cleared in a
single sitting:

```
> **Shelf-Status**: blocked
> **Blocked-On**: owner-ops
```

| Gate               | Meaning                                                            |
| ------------------ | ------------------------------------------------------------------ |
| `none`             | No external gate — pickable now; backlog, not a blocker            |
| `time-window`      | Waiting for a measurement or evidence window to elapse             |
| `owner-ops`        | Needs a host/infra change no agent can reach (cron, secrets, DNS)  |
| `owner-cloud`      | Needs an owner-run `terraform apply`, real credentials, or prod    |
| `product-decision` | Waiting on an owner/product call, not a technical prerequisite     |
| `upstream`         | Waiting on a third party — a dependency release, a vendor ticket   |
| `unclassified`     | Blocked, but the doc does not say by what — **fix this**           |

**A gate is never inferred from prose.** A mis-guessed gate is worse than an honest
`unclassified`: a plan filed under the wrong session is a plan nobody picks up.

## Queue Order — What Gets Built First

`ready` says a plan _may_ be handed to an agent. It does not say **when**. Without an explicit
order the queue is decided by an accident of two defaults — filename sort in the index
generator, priority-then-slug in whatever consumes it — and once several plans share a
priority, the alphabet chooses what gets built.

So every `ready` plan carries an explicit position, immediately after its `Priority` line:

```
> **Priority**: Critical — three downstream plans are blocked on it
> **Queue-Order**: 20
```

**Lower runs earlier. Use gaps of 10** so a plan can be slotted between two others without
renumbering the queue. The sort key is `(queue_order, priority, slug)`:

| Key           | Answers                             | Why it is not enough alone       |
| ------------- | ----------------------------------- | -------------------------------- |
| `queue_order` | what to build **first**             | absent on older plans            |
| `priority`    | how much a plan **matters**         | several plans honestly share one |
| `slug`        | keeps equal ranks **deterministic** | arbitrary                        |

`queue_order` **outranks** `priority`: a numbered `low` plan runs before a worse-numbered
`critical` one, because somebody chose the number. An unnumbered plan never displaces a
numbered one, whatever its priority — absence is not a choice, so it sorts last.

**The order is resolved from one place** (`scripts/docs/queue_order.py`) and **imported** by
every consumer, never reimplemented. A published order that is not the real order is worse
than no order, because it invites planning around a sequence nobody will follow.

## Reports Are Release-Anchored

A report describes a **commit range bounded by release tags**, never "everything since this
last ran". A window that straddles a release boundary cannot answer the only question that
matters about a finding — _is this in production right now?_

| State         | Window               | Location                                | Refresh                       |
| ------------- | -------------------- | --------------------------------------- | ----------------------------- |
| **in-flight** | `<latest tag>..HEAD` | `docs/reports/regular/<name>.md`         | overwritten by every run      |
| **released**  | `<prev tag>..<tag>`  | `docs/reports/releases/<tag>/<name>.md`  | **frozen — never edited**     |

Cadence does not change: a weekly job still runs weekly. Only the *window it describes* moved
from "since last run" to "since last release".

Resolve the window from **one place** — `scripts/docs/release_window.py`, so every consumer
computes it once rather than deriving it five ways:

```bash
{{CLI}} docs release-window                    # the in-flight window as JSON
{{CLI}} docs release-window --apply            # stamp the anchor onto regular/*.md
{{CLI}} check reports                          # validate every anchor (blocks CI)
```

**At a release the window closes**, and the editions become the permanent record of that build:

```bash
# 1. narrative pass — rewrite each report's prose for the closing window (not mechanical)
# 2. mechanical freeze — archive, re-anchor regular/ to the new window, rebuild the index
{{CLI}} docs freeze-release --tag v1.4.0
{{CLI}} docs freeze-release --tag v1.4.0 --dry-run
```

Do the narrative pass **first**. A frozen edition carrying a window it does not describe is
worse than an unfrozen one, because it looks authoritative. The freeze refuses a tag that is
already frozen, and it commits nothing — read the diff.

**Never edit anything under `docs/reports/releases/`.** A correction to a shipped release's
report goes in an `## Errata` block on the *current* in-flight edition, naming the release it
corrects. Rewriting a frozen edition destroys the audit trail the anchoring exists to create.

Occasional reports keep date-based filenames — they are point-in-time investigations, not
windows — but must name the build they analyzed: `> **Analyzed at:** v1.4.0 +38 commits`.

## Where an Investigation's Findings Go — Route Them, Don't Log Them

The expensive half of an audit is not what it finds — that becomes an issue — it is what it
**rules out**. A verified "I looked and it is not that" costs the same as a finding and
evaporates when the session ends, so the next sweep pays for it again.

| The finding is about                        | It goes                                      |
| ------------------------------------------- | -------------------------------------------- |
| a bug you filed                             | a comment on that issue                      |
| how a piece of code behaves                 | that code's docstring                        |
| an option a plan considered and dropped     | a `## Dropped … and why` section in the plan |
| a whole sweep, or a hunt that found nothing | `docs/reports/occasional/<date>-<slug>.md`   |

**Read `docs/reports/occasional/` before starting a sweep.** Re-running one cold is the most
expensive way to learn what an `ls` would have told you.

**Do not add a central investigations log or registry.** Forgetting to update a registry is
the same class of bug the rest of this document exists to remove — and a log is a registry
with worse odds, because it is updated at the end of a hunt when attention is lowest. Routing
a finding to the artifact that owns it needs no upkeep: that artifact is already being read.

## Regenerating the Indexes

After adding or changing any plan under `docs/TODO/` or `docs/implementations/`:

```bash
{{CLI}} docs index          # frontmatter backfill + both JSON indexes + both READMEs
{{CLI}} docs index --check  # are they stale? (leaves the tree untouched)
```

## Filing a Completed Plan

```bash
{{CLI}} docs file <slug> --category <category>   # git mv + every regeneration
{{CLI}} docs file <slug> --dry-run               # what it would do, changing nothing
```

It refuses a plan that still has unchecked tasks, and it commits nothing — read the diff.

**Then repoint what cited it.** The move breaks links in two directions, and both are
load-bearing prose that records *why* the docs say what they say:

```bash
{{CLI}} check doc-refs    # docs/* paths cited from source comments
{{CLI}} check doc-links   # relative markdown links between docs (+ #fragments)
```

**Repoint, never delete.** A link whose target is genuinely gone gets its sentence rewritten
— repointed to the successor, or de-linked to a backticked path plus the commit that removed
it, so a reader can still find it in history.

## Resolving Conflicts in Generated Docs

The four generated artifacts collide in **any** two branches that touch the docs trees:

| Generated artifact               | Produced by                           |
| -------------------------------- | ------------------------------------- |
| `docs/todo_index.json`           | `scripts/docs/gen_todo_index.py`      |
| `docs/TODO/README.md`            | `scripts/docs/rebuild_todo_readme.py` |
| `docs/implementation_index.json` | `scripts/docs/gen_impl_index.py`      |
| `docs/implementations/README.md` | `scripts/docs/rebuild_impl_readme.py` |

**Never hand-resolve one.** The correct resolution is never a blend of the two texts — it is
always "regenerate from the merged sources". Hand-resolving is also how work gets silently
reverted, because the stale result lands inside a file nobody reviews.

`.gitattributes` routes all four through the `regen-docs` merge driver, which takes the
incoming side wholesale and records that a regeneration is owed. The driver definition lives
in `.git/config`, which is **not** version controlled:

```bash
{{CLI}} check merge-drivers                     # installed? regenerations owed?
python scripts/git/install_merge_drivers.py     # install / repair by hand
```

## Adding a New Top-Level Doc

Register it in **both** index tables — `CLAUDE.md`'s Documentation Reference and
`.github/DOCS_INDEX.md`. `{{CLI}} check docs` fails if a `docs/*.md` exists in neither.
