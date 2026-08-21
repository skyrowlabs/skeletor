# Tiers — What Each One Buys, and What It Costs

Three cumulative tiers. Pick the one you will **maintain**, not the one that
looks most thorough.

> **An unmaintained gate is worse than an absent one.** It is red for reasons
> nobody remembers, so people learn to expect red, and then a real failure looks
> exactly like the noise. Every tier below is a promise to keep something green.

```bash
bin/skeletor-new ../my-project --tier core       # default
bin/skeletor-new ../my-project --tier governed
bin/skeletor-new ../my-project --tier agentic
```

Tiers compose in order (`agentic` includes `governed` includes `core`), and a
language overlay (`--language python|node|both|none`) is applied on top.

---

## Tier 1 — `core`

**Take this always.** Nothing here needs a team, a budget, or a running service,
and every piece pays for itself inside a week.

| You get                          | It buys                                                       |
| -------------------------------- | ------------------------------------------------------------- |
| `.claude/rules/*.md`             | Conventions an agent loads every session, one file per domain |
| `CLAUDE.md` + `DOCS_INDEX.md`    | Lazy doc loading — 15–40K tokens per task instead of all of it |
| `docs/TODO/` + `implementations/` | A backlog with a shape, and an archive of *why*               |
| Generated indexes + READMEs      | "Is this already built but parked?" answerable from one JSON  |
| Conventional commits + Release Please | Versioning and a changelog nobody hand-writes            |
| `./<cli>` wrapper + `cli/` package | One discoverable entry point; commands register by existing  |
| Marker-based test suites         | A test file joins a suite by existing — no registry           |
| `require_or_skip`                | A skip in CI becomes a failure, so "green" means "ran"        |
| Doc link / ref / table checkers  | Filing a plan stops silently rotting links in two directions  |
| `ci.yml` with a gate job         | Draft PRs cost ~1 minute; ready PRs cost what they earn       |
| `bug` capture command            | An out-of-scope bug leaves the session without widening it    |

**Cost**: about a day to internalise. The docs lifecycle is the only part with a
learning curve, and `{{CLI}} docs file` removes most of it.

**Skip it only if** the project will never have more than one plan, one doc and
one contributor — in which case you do not need a shell.

---

## Tier 2 — `governed`

**Take this when a second person or a second agent touches the repo**, or when
CI minutes start costing money.

| You get                               | It buys                                                    |
| ------------------------------------- | ---------------------------------------------------------- |
| `.claude/rules/shared-tree.md`        | The rule that stops one agent deleting another's work      |
| `<cli> commit`                        | Commits without pre-commit's repo-wide stash               |
| `<cli> worktree`                      | A checkout per branch; refuses to drop unpushed commits    |
| `scripts/tree_lock.py`                | Advisory holds, so jobs have a fact to refuse on           |
| `check_workflow_drift.py` + allowlist | Two jobs that boot the stack cannot silently diverge       |
| `coverage-nightly.yml`                | The expensive suites, off the pre-merge path               |
| Skip + coverage ratchets              | Slippage becomes a number somebody has to change on purpose |
| Dependabot + CODEOWNERS + templates   | Bumps that actually run the suite; issues that can be acted on |

**Cost**: the ratchets need a baseline set honestly on adoption, and the drift
allowlist needs its reasons kept current. Budget an hour a month.

**Skip it if** you are the only person and the only agent, and CI is free at your
volume. Add it the day either stops being true.

---

## Tier 3 — `agentic`

**Take this when the repo has slow-moving problems nobody will choose to look
for on a Tuesday** — dependency drift, doc rot, an ageing backlog, test gaps.

| You get                            | It buys                                                     |
| ---------------------------------- | ----------------------------------------------------------- |
| `.claude/agents/*.md`              | Focused subagents: implementer, tester, documenter          |
| `/implement` skill                 | A plan driven end-to-end and **filed**, not just written    |
| `/release` skill                   | A release as a phased state machine that stops for a human  |
| `scripts/reporting/jobs.py`        | One registry generating crontab + CLI + status viewer       |
| `agent_runner` + `run_ledger`      | Collection/triage split, blast-radius policy, outcome rails |
| Release-anchored reports           | Every finding scoped to "is this in production right now?"  |
| One fully-worked example job       | The shape to copy — registry, module, prompt, heartbeat     |

**Cost**: real. A scheduled agent commits to your repo unattended. You need a
heartbeat monitor per job, a place for findings to go, and the discipline to read
the ledger. The source repo reached 25 jobs over a year; **start with one** and add
another only when the first has been useful for a month.

**Skip it if** nothing yet rots on its own. Automation that reports on an empty
repo teaches you to ignore its reports.

---

## Choosing by symptom

| Symptom                                                        | Tier       |
| -------------------------------------------------------------- | ---------- |
| "I rebuilt something that already existed, parked"             | `core`     |
| "Nobody remembers why this is like this"                       | `core`     |
| "The docs are wrong and nothing said so"                       | `core`     |
| "CI bills are surprising"                                      | `core`     |
| "Two agents overwrote each other"                              | `governed` |
| "It passes locally and fails in CI"                            | `governed` |
| "Coverage/skips got worse and nobody noticed"                  | `governed` |
| "Dependencies drift until something breaks"                    | `agentic`  |
| "The backlog is a folder nobody triages"                       | `agentic`  |
| "Reports exist but describe an unknown build"                  | `agentic`  |

---

## Adding a tier later

Tiers are plain file overlays, so upgrading is a re-run into the existing tree:

```bash
bin/skeletor-new . --tier governed --force --no-git \
  --name "..." --cli "..." --slug "..."     # same values as the original run
```

Pass the **same** substitution values, or the overlay will render placeholders
differently from the files already there. Review the diff before committing:
`--force` overwrites files a later overlay also ships.
