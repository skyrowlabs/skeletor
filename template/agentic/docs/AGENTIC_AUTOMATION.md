# Agentic Automation

The project's **self-maintenance system**: registered jobs that watch the repo,
form a judgement about what they find, and act on it.

Each job pairs a **deterministic collection stage** (stdlib Python, no
dependencies, same answer twice) with an **agentic triage stage** — a headless
agent that reads the collected data, makes the calls a script cannot, writes a
report, and commits it.

The separation is the design. A job that skips collection and asks an agent to
go and look produces a different answer every night, and none of them are
reproducible.

---

## The live schedule

The schedule is **generated from one registry** —
[`scripts/reporting/jobs.py`](../scripts/reporting/jobs.py) — and rendered by
`{{CLI}} report cron --print`. That registry is the source of truth for the crontab,
the `{{CLI}} report` subcommands, and the status viewer, so those three cannot drift
apart (`tests/test_reporting_jobs.py` asserts it).

```bash
{{CLI}} report cron --print    # emit the block for `crontab -e`
{{CLI}} report cron --check    # does the LIVE crontab match the registry?
{{CLI}} report watch           # what ran recently, and what it decided
```

**Any table in this document is documentation; the registry is the system.**
Never hand-copy a schedule from prose into a crontab, and remember that
*registered* is not *installed in your crontab*. When the two disagree,
`cron --check` tells you which one your machine is actually following.

## The grid is load-bearing

Two rules generate it, and both are about a resource nothing locks: **one shared
working tree**.

1. **Only one committing job in flight at a time.** Nearly every job spawns an
   agent that edits and commits the same tree, and several regenerate the same
   derived docs. Run concurrently, they race on git and on those files — and the
   loser's work vanishes with no error. Jobs that commit nothing may share a
   window.

2. **Weekly work is partitioned by weekday.** One lane per weekday, sized at
   several times the observed run length. The margin is the point: a block sized
   to today's runtime is a bet that runtime never grows, and it leaves no room
   for the next job. Scheduling as a mutex only works while somebody re-derives
   the whole grid each time a job is added — and that is exactly what stops
   happening.

The nightly spine is a **pipeline**: agents commit → a gate checks what they
committed → a repair job fixes what the gate found → a digest reports the night
as a closed set. Putting the heavy agents *after* the gates would leave every
agent commit ungated until the following night.

## Detection latency should match consequence latency

This is the rule that decides where a check belongs. Nothing on the integration
branch reaches a user until a release, so **a check belongs on a nightly (or on
the release train) unless its cost grows before then**. Two kinds of thing do
grow, and stay fast:

- A **whole-project** gate, where one error blocks every commit repo-wide.
- **Security advisories**, where the window is the exposure.

Everything else is detection at ≤24h, and that is a deliberate trade, not a gap.

## A job that cannot answer correctly declines

`declined` is a first-class outcome, distinct from `failed`. A job that finds the
tree on the wrong branch, or holding somebody's uncommitted work, **stands down,
records why, and still pings its heartbeat** — because a job that executed and
chose not to answer must stay distinguishable from a dead cron.

**Refuse, don't warn.** A job that declines costs you a cycle and nothing else. A
job that warns and proceeds produces a **verdict**, and a wrong verdict is read
as a right one. The two outages behind this rule both had a scheduled job grade
whatever branch the shared tree was sitting on and report green while the real
base branch was failing — and both errors flattered the base branch, which is
the direction that ships something broken.

## Two rails on the outcome record

Enforced once, in [`run_ledger.py`](../scripts/reporting/run_ledger.py), so a new
job cannot forget them:

- **A job whose agent never ran must not report `ok`.** A collection stage that
  succeeded and a triage stage that never started look identical from outside,
  and the second is a job that has quietly stopped working.
- **A red gate may not report `ok`.** A job that finds a problem and records
  success has inverted its own purpose.

## Remediation — what a job may fix itself

Every job carries a `fix_policy`, and it **defaults to `none`**. A job added
without thinking about blast radius gets no autonomy rather than inheriting
whatever the entry above it had.

| Policy       | May                                                          |
| ------------ | ------------------------------------------------------------ |
| `none`       | Report only; never write to the repo                         |
| `own-report` | Write and commit its own report file, nothing else           |
| `docs`       | Repair generated docs and commit them                        |
| `code`       | Open a pull request; never merge, never push to a protected branch |

The policy is passed to the agent **explicitly** in its prompt — an agent that
does not know its blast radius will pick one. What exceeds the policy is
escalated as a finding, not acted on: an unattended change nobody authorised is
worse than a finding nobody acted on.

## cron does not give you your login PATH

A job that works in your shell and not under cron is almost always this, and it
fails by not finding an interpreter — which reads as a broken job rather than a
broken environment. The generated crontab block sets `PATH` explicitly for
exactly this reason; `tests/test_reporting_jobs.py` asserts it still does.

---

## Adding a job

1. Add a `Job(...)` entry to `scripts/reporting/jobs.py`. **Decide its
   `fix_policy` explicitly.** Name the prompt file after the module
   (`prompts/<module>.md`) — that is how the policy is resolved.
2. Write `scripts/reporting/<module>.py` with a `main()`: deterministic
   collection, then `agent_runner.run_triage(<key>, collected)`.
3. Write `scripts/reporting/prompts/<module>.md`. State what **not** to write as
   explicitly as what to write — an unconstrained report is padded to look
   substantial and is not read next week either.
4. Add its heartbeat variable to `.env.example`.
5. If it writes into `docs/reports/regular/`: **seed the report file** and add
   its filename to `ANCHORED_REPORTS` in `scripts/docs/release_window.py`, so
   the window is stamped and the release freeze archives it. Then have the
   prompt re-stamp **only** that report (`--apply --only <name>.md`) — a bare
   `--apply` dirties every anchored report, and a job that then commits just its
   own leaves the rest claiming a refresh that never happened.
6. If it should not be scheduled yet, add it to
   `scripts/reporting_schedule_allowlist.yaml` **with a reason**. Otherwise
   re-run `{{CLI}} report cron --print` and reinstall the crontab.

Steps 1–5 are cross-checked by `tests/test_reporting_jobs.py`. Only step 6's
crontab half is unenforceable from here — it is a change to a crontab on a host
this repo cannot see.

---

## What this is not

It is not a replacement for review, and it is not a way to get more work done
unattended. It is a way to make the repo's **slow-moving problems visible on a
schedule** — the ones nobody would ever choose to look for on a Tuesday, and
which are therefore found by accident, late, or never.
