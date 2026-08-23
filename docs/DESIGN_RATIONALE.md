# Design Rationale — Where Each Mechanism Came From

Every mechanism in this shell was extracted from one mature production
repository, reviewed at ~945 merged pull requests and two years of iteration.
Nothing here was designed up front: each rule is a scar, and the useful ones say
so in their own comments.

This document records **what went wrong without each mechanism**, so you can
decide fairly whether it earns its place in your project. This is the evidence behind
every choice in [`SETUP_GUIDE.md`](SETUP_GUIDE.md) and [`TIERS.md`](TIERS.md) —
read it when you want to know *why* a rule is shaped the way it is, or when you
are deciding whether to drop one.

**Scale, for calibration**: ~945 merged PRs, 482 test files, 165 CLI commands,
25 scheduled jobs, ~543K tokens of documentation across 20 top-level docs, and
five services. Almost nothing here was designed up front. Each mechanism is a
scar, and the useful ones say so in their own comments.

---

## The one idea underneath everything

> **A rule that two files can express is a rule that will drift, and the copy
> that is wrong is always the one being read.**

Every significant mechanism in this shell is an application of this:

| Two copies that drifted            | What replaced them                              |
| ---------------------------------- | ----------------------------------------------- |
| Crontab string + CLI commands      | `scripts/reporting/jobs.py` — both derived      |
| README queue order + job's sort     | `scripts/docs/queue_order.py` — both import it  |
| Five ways to compute "since when"   | `scripts/docs/release_window.py`                |
| Dev compose file + CI compose file  | `check_compose_drift.py` + a reasoned allowlist |
| Two workflows booting the stack     | a composite action + auto-enrolled drift check  |
| Host mirror of a CI action          | `MIRRORS_ACTION_STEPS`, checked against the action |
| Docs-only pattern in two workflows  | `.github/scripts/docs-only.cjs`, required by both |
| 25 hand-derived project roots       | `scripts/paths.py` — one derivation, everything imports |

The corollary is stated explicitly in `CLAUDE.md` Rule 11 and is the single most
transferable sentence in the repository:

> **Enrollment is deliberately not a registry — forgetting to update a registry
> is the same bug.**

Where the source repo needs a set of things checked, it *discovers* the set by pattern
(any job that runs `docker compose up`; any test file with a `pytestmark`) rather
than maintaining a list. Exemptions go in an allowlist **with a written reason**,
so an intended divergence is a decision record and an unintended one is a
failure.

---

## Documentation as a lifecycle, not a folder

This is the part most worth stealing, and the part almost no project has.

**Two trees, one flow.** `docs/TODO/` is the *holding tank* — everything not
finished. `docs/implementations/` is the *archive* — only completed work. A plan
**moves** between them; it never copies. Both have generated READMEs and
generated JSON indexes.

That structure buys three things that are hard to get any other way:

1. **"Is this already built but parked?"** is answerable by reading one JSON
   file rather than by asking someone who was there. In a repo with ~230 plans,
   this is the difference between rebuilding a feature and un-shelving it.
2. **Why the system is the way it is** survives. The archive's `agent_value`
   rating (1–3) tells a reader which docs to read *before* modifying a system.
   The plan template's `## Dropped, and why` section is what stops a design
   being re-litigated every time somebody new touches it.
3. **The backlog has a shape.** `shelf_status` says *why* something is
   unfinished; `blocked_on` says *what would unblock it*, so plans sharing a gate
   clear in one sitting; `queue_order` says *what gets built first*.

**The queue-order story is the clearest single lesson in the repo.** On
2026-08-17, seven of ten `ready` plans were priority `high`. The nightly builder
sorted by `(priority, slug)`; the published README sorted by priority alone. The
result: the README advertised positions `30, 50, 60, 40, 90` while the job would
build them `30, 40, 50, 60, 90` — four rows of a published queue in an order
that would never happen. And a foundational plan four other plans depended on sat
third, behind a plan large enough to exhaust the run budget. *Nobody chose that;
the alphabet did.*

The fix has three parts, and all three transfer:

- An explicit number, **never inferred** — a guessed running order is precisely
  the accident being replaced.
- Absence sorts **last** (`UNORDERED = 10_000`), because absence is not a choice.
- The sort lives in one module that both consumers **import**.

**Reports are anchored to release tags, not to "since this last ran".** A window
that straddles a release boundary cannot answer the only question that matters
about a finding: *is this in production right now?* In-flight reports live in
`docs/reports/regular/` and are overwritten; at a release they freeze into
`docs/reports/releases/<tag>/` and are never edited again. A correction to a
frozen edition goes in an `## Errata` block on the current one.

**Findings get routed, not logged.** Bug hunts recur, and the expensive half is
what they *rule out* — which evaporates when the session ends. The source repo routes
each finding to the artifact that owns the question (the issue, the docstring,
the plan's dropped-options section, or an `occasional/` report) and explicitly
**refuses to add a central investigations log**, on the grounds that a log is a
registry updated at the end of a hunt when attention is lowest.

### What does not transfer

The sheer volume. `docs/API.md` is 430KB; the full docs tree is ~543K tokens.
That is a consequence of five services and two years, not a target. What
transfers is the **lazy-loading index** (`.github/DOCS_INDEX.md`) that makes the
volume affordable — a typical task loads 15–40K tokens instead of 543K.

---

## Code governance

**Blocking set, kept small and absolute.** flake8 `E9,F63,F7,F82,F401` (syntax
errors, undefined names, unused imports), isort, black at 127 columns, and
pyright in `standard` mode. Complexity over 15 is *flagged, never blocked* — the
distinction between "must fix" and "worth knowing" is maintained deliberately.

**Pyright is whole-project in both places that run it**, and both block. The
consequence is stated rather than hidden: *one stale error anywhere blocks every
Python commit repo-wide, including commits that touch nothing near it.* That is
described as intended pressure, not a bug.

The most transferable observation in `.claude/rules/python.md` is about
environments, and it is genuinely counter-intuitive:

> `reportMissingImports` is `none`, so a package pyright cannot import becomes
> `Unknown` and stops constraining anything. **This cuts both ways** — a leaner
> environment is not a more permissive check, just a different one. A machine
> with `redis` installed sees `bytes | str` errors a bare checkout does not; a
> machine *without* `pytest` sees "possibly unbound" errors across `tests/` that
> nobody else gets.

Hence `.github/pyright-deps.txt`, a test asserting every type-checking workflow
installs from it, and a rule to pass `--pythonpath` when reproducing a CI result.

**Tool versions are pinned in one file** (`.pre-commit-config.yaml`) and mirrored
into requirements and CI, with `tests/test_lint_tool_parity.py` failing on
divergence — *and the rule explicitly notes the test cannot pin your local venv*,
which is where the real failure comes from: two isort majors disagree about
parenthesised imports across 33 files.

**A JS lint ratchet rather than a target.** ESLint runs with `--max-warnings=<n>`
where `n` is what was inherited. The gate is whole-tree (`--max-warnings` cannot
be apportioned per file), so the hook's file pattern decides only *whether* to
run — a Python-only commit matches nothing and pays nothing.

---

## Output: two streams, one vocabulary

This is the one mechanism here that was **not** extracted from the source
repository. Its incident happened in this shell, which is the only reason it is
worth reading: it is what the failure looks like when the discipline is missing
from a codebase that is otherwise entirely about that discipline.

`cli/helpers.py` shipped `ok()` / `fail()` / `warn()` from the first commit.
Roughly twenty call sites across `scripts/` printed `f"✅ ..."` by hand anyway —
not out of carelessness, but because **`scripts/` could not import `cli/`**. The
dependency runs one way only, so half the tree could not reach the vocabulary,
and a vocabulary half the tree cannot reach is one the other half reinvents.

What that cost, measured in the template as it stood:

| Symptom                                             | What it actually was                        |
| --------------------------------------------------- | -------------------------------------------- |
| `⏸️` defined in no file, spelled in three            | two spellings already differed by a space    |
| The gate table reimplemented in `cli/commit.py`      | a second renderer of one result             |
| `--json` on four scripts, parseable on one           | JSON and `❌` lines sharing one stdout       |
| No `--json` on either ratchet                        | the two numbers a dashboard most wants       |

None of it is visible to a linter or to review, because every individual file is
internally consistent. That is the same shape as the compose-drift bug, and it
gets the same treatment.

**The fix is a stream split, not a style guide.** `scripts/output.py` owns the
symbols and the streams: status and narration to **stderr**, payload and
listings to **stdout**. Both still land on a terminal, so an interactive run
looks unchanged. What changes is that `--json` stops needing a second code path —
build the result object, `emit` it, render the human half exactly as before. The
early `return` that three scripts were missing is no longer a thing to remember.

That is the transferable half: **the reason to separate the streams is not
tidiness, it is that it makes the machine-readable flag free.** A `--json` that
costs a branch per exit path gets added to the scripts somebody happened to need
it on, and those are never the ones a dashboard asks for later.

Enrolment in `check_output_discipline.py` is by pattern — every `.py` under
`cli/` and `scripts/` — with exemptions in an allowlist with a written reason.
It flags a state symbol typed into a `print`, a stream picked by hand, and a
`check_*.py` with no `--json`. `tests/test_output_contract.py` then *runs* each
checker and parses the result, because a payload can be well-shaped in the
source and still unusable in practice, which is exactly what had happened.

---

## Testing

**Registration is marker-based, and this is the strongest single pattern.**

```python
pytestmark = [pytest.mark.integration]
```

A test file joins a suite **by existing**. No CI step per feature, no runner
case, no CLI entry. `tests/test_marker_coverage.py` fails the unit suite if a
file declares none. The rule is stated flatly: *"Never add per-feature CI steps,
`run_tests.sh` cases, or `cli/test_cmds.py` entries. Those registries are dead —
the marker is the registration."*

**`require_or_skip` instead of `pytest.skip`.** It skips locally and **fails**
under the CI flag, because CI guarantees the services — so a skip there means the
harness broke, and a harness that silently skips its whole suite reports green.

**Ratchets on both skips and coverage**, with the reasoning attached: a skip
budget exists because a run reporting "340 passed, 176 skipped" reads as green;
a coverage budget is *"a ratchet, not a target — never chase a number"*.

**Teardown discipline, stated as a principle**: *"a startup nuke is not a
teardown."* A full run once left 70 accounts behind, hidden for days by a
purge-at-boot that made the leak invisible.

**`filterwarnings = error::pytest.PytestReturnNotNoneWarning`**, with the reason:
14 tests `return`ed instead of asserting, so they could not fail. Making it an
error now means the class breaks on our schedule rather than during a version
bump.

**A per-test timeout, sized against CI and not local runs.** The comment is
explicit that 120s was first justified from a local run where the slowest call
was 8.5s — a margin that looked enormous and was not, because the same suite's
slowest calls in CI are 21–23s. It exists *to name a hang, not to police
slowness*, and it is declared as an ini key rather than a `--timeout` flag
because an unknown ini key is a warning without the plugin while an unknown CLI
flag is a hard error.

---

## CI, cost, and the draft-PR discipline

This is where the source repo has the most numbers behind it, and it is the section
most likely to save a new project real money.

**The two facts everything follows from:**

1. **Requiring a status context costs nothing; only *running* a job does.** A
   required context satisfied by a `skipped` report still satisfies branch
   protection. `develop`'s required list was once trimmed "for cost" — it saved
   nothing and broke the Dependabot gate. *Size the required list for what must
   gate; never trim it for cost.*
2. **A `synchronize` event on a *ready* PR re-runs everything.** In the
   2026-08-01→09 window every PR was opened ready and the 13-minute integration
   suite re-ran on each corrective push, four to six times per PR. Two PRs
   opened and merged the same day burned 285 minutes between them, and **42% of
   all Actions minutes ended in a failed or cancelled run.**

So: **open every PR as a draft**, iterate, flip to ready once. A draft runs the
gate job alone (~1 billable minute). Nothing is un-gated by this — GitHub blocks
merging a draft regardless, and `ready_for_review` fires the full set.

**What runs is computed once, in a gate job, and every expensive job is gated on
its output.** Three subtleties, each of which was a bug first:

- Skipping is done with `if:` **at the job level, never `paths-ignore` on the
  trigger** — a required check that never *reports* blocks the PR forever, while
  one that reports `skipped` passes.
- `ready_for_review` in the trigger `types:` is **load-bearing**. Remove it and
  the gated jobs never re-run when a PR leaves draft; they stay `skipped`, branch
  protection accepts that, and the PR merges having run nothing. A test pins it.
- The docs-only detector is **fail-open**: an API error, an empty file list, or
  one unrecognised path runs the full pipeline, because a false positive skips
  lint, tests *and* security **and marks them satisfied**.

**The Dependabot exemption is a mechanism, not a courtesy.** Auto-merge fires the
moment branch protection is satisfied. The exemption makes integration *run* on a
bump; requiring the integration context is what makes auto-merge *wait* for it.
Remove either half and a bump merges untested. Its author test is two-part —
`dependabot[bot]` **or** the combine-PRs head ref — because the batching action
opens the combined bump under whoever ran it.

**`strict` (require-branches-up-to-date) differs by branch, deliberately.** On
`main` it is kept, because the release PR genuinely must be current. On `develop`
it is off: every merge invalidates every other open PR, so a queue of N PRs costs
N re-runs and drains one at a time, and GitHub's merge queue needs an Enterprise
plan.

**The organising principle for *where* a check belongs:**

> **Detection latency should match consequence latency.** Nothing on the
> integration branch reaches a user until a release, so a check belongs on the
> nightly or the release train **unless its cost grows before then**.

Two things do and stay fast: whole-project pyright (one error blocks everyone)
and security advisories. Everything else moved to host cron, and the trade is
stated as a trade — "detection at ≤24h, not a pre-merge gate" — rather than
presented as free.

**One catch-net could not move to the host**, and the reasoning is worth keeping:
a nightly host job cannot see a failure that only happens in a CI environment. On
2026-08-12 a green host sentinel sat on a red `develop` for nine hours for
exactly that reason, so one workflow re-runs the unit job *on a runner*.

---

## The agentic layer

Twenty-five registered jobs, each pairing **deterministic collection** (stdlib
Python, no dependencies, reproducible) with an **agentic triage stage** (a
headless `claude -p` that reads the collected data and writes a report).

The separation is the design: a job that skips collection and asks an agent to go
and look produces a different answer every night, none of them checkable.

**What transfers even at small scale:**

- **One registry** (`jobs.py`) generating the crontab, the CLI subcommands and
  the status viewer, with tests asserting all three agree.
- **`fix_policy` defaults to `none`.** *"A job added without thinking about blast
  radius gets no autonomy rather than inheriting the previous entry's."* The
  policy is passed to the agent explicitly, because an agent that does not know
  its blast radius will pick one.
- **`declined` is a first-class outcome**, distinct from `failed`, and it still
  pings the heartbeat — an executed-and-declined job must stay distinguishable
  from a dead cron.
- **Refuse, don't warn.** Two independent outages: `release_train` on 2026-08-16
  graded whatever feature branch the shared tree was sitting on and reported the
  unit suite green while `develop` failed 21 tests; `integration` did the same on
  2026-08-19. *"Both errors flattered `develop`, which is the direction that
  ships something broken."*
- **Two ledger rails.** A job whose agent never ran must not report `ok`; a red
  gate may not report `ok`.
- **cron does not give you your login PATH** — a job that works in your shell and
  not under cron is almost always this, and it fails by not finding an
  interpreter, which reads as a broken job.
- **Timezone must be named, never implicit.** A bare `datetime.now()` is local on
  the host and **UTC** on a runner; that shipped a test file which passed locally
  and failed in CI for thirteen hours every Saturday.
- **Monthly jobs ride a weekly lane plus a `first_week_only` gate**, because cron
  ORs day-of-month against day-of-week — "first Sunday" is not expressible.
- **The grid is a mutex.** One committing job in flight at a time, weekly work
  partitioned by weekday, lanes sized at ~9× the observed run. The margin is the
  point: a block sized to today's runtime is a bet that runtime never grows. When
  the Saturday sweep was added months after `agent-fix`'s five-hour budget was
  set, nobody resized it, and on 2026-08-14 the 19:00 job was still holding the
  tree at 22:50.

**What does not transfer to a new project**: the volume. Twenty-five jobs, a
release train, a fix-queue drainer and a plan-implementing job are the output of
a year of iteration on a repo with a real user-facing product. Start with one.

---

## The shared-tree problem — the newest and least obvious lesson

Multi-agent work introduced a failure class that single-developer repos do not
have: **a `git checkout` underneath another agent destroys uncommitted work with
no error.** On 2026-08-15 that happened twice in one session to the same file,
and a commit from that session landed on an unrelated agent's branch.

Three mechanisms, and the reasoning for each is unusually good:

- **A scoped commit command** (`<cli> commit`) exists because pre-commit **stashes every unstaged change in
  the repo** while its hooks run — so a plain `git commit` deletes another
  agent's in-flight work from disk for ~30s and silently discards anything they
  write in that window, on unrelated files. The scoped command runs the same hooks
  against only the named paths, then commits with `--no-verify`.
- **Advisory locks, not enforcing ones.** *"A lock that can refuse the owner's
  own command is a lock people learn to route around."* Nothing blocks an
  interactive `git checkout`; what the records buy is that scheduled jobs have a
  fact to refuse on.
- **Two hold kinds** — `suite` and `edit` — because the 2026-08-15 incident had
  no suite running, just an editor. *"A clean `git status` is not evidence that
  nobody is working here."*
- **`would_strand()` refuses on a branch it cannot read**: a false refusal costs
  one retry, a false clearance costs somebody's work.
- **The commit command reads the branch twice**, before and after its checks, because
  the checks take tens of seconds and that window is the whole exposure.

Worth noting what the source repo says about *when* to take a worktree: **not by
reflex.** "This is a single-developer repo; a small, self-contained, locally
verified change lands straight on `develop`. A worktree implies a branch, so
taking one by reflex reintroduces exactly the branch-and-PR ceremony the owner
has already called wasted effort once."

---

## Versioning

Conventional Commits → Release Please, `release-type: simple`, `VERSION` file,
generated `CHANGELOG.md`, `bump-minor-pre-major: true` (pre-1.0, `feat` bumps
minor and `fix` bumps patch). `test`/`build`/`ci`/`chore` are hidden from the
changelog but still recorded.

The rules that matter are two lines: **never hand-edit `CHANGELOG.md`**, and
**`docs:` for `docs/**` changes only, never `feat:`** — which would trigger a
version bump for a prose edit.

The commit-msg hook rejects any message with **more than one subject line**. That
is the rule people are surprised by, and it is the one that matters: a message
with three `feat:` lines is three commits wearing one hat, and the changelog
generator takes only the first.

---

## Honest assessment: what is over-built

Not everything here is worth copying, and the shell reflects that.

| Mechanism                              | Verdict for a new project                          |
| -------------------------------------- | -------------------------------------------------- |
| Marker-based test registration         | **Take immediately.** Free, and it never rots.     |
| Conventional commits + Release Please  | **Take immediately.** An afternoon, permanent.     |
| TODO/implementations lifecycle         | **Take immediately.** Worth it at ~5 plans.         |
| Lazy-loading docs index                | **Take at ~5 docs.** Before that, `ls` is fine.     |
| Draft-PR discipline                    | **Take when CI costs money.** Which is soon.       |
| `require_or_skip`                      | **Take with the first integration test.**          |
| Doc-link + source-ref checkers         | **Take when you first file a plan to the archive.** |
| Ratchets (skip / coverage / lint)      | **Take when adopting into an imperfect codebase.**  |
| Queue order + blocked-on gates         | **Take at ~10 plans.** Pointless at three.          |
| Release-anchored reports               | **Take when something writes reports on a cron.**   |
| Shared-tree locks + scoped commit      | **Take when a second agent runs concurrently.**      |
| Compose/workflow drift checks          | **Take at the second copy**, not before.            |
| One output module + stream split       | **Take on day one.** It is an hour, and it is what makes `--json` free later. |
| 25 scheduled jobs                      | **Do not copy.** Start with one and earn the rest. |
| A 430KB API doc                        | **Not a target.** A consequence.                    |
| A 165-command CLI                      | **Not a target.** The *rule* is what transfers.     |

The one habit to carry over regardless of scale is the **habit of writing the
reason next to the rule**. Nearly every config file in the source repo explains itself
— `.flake8` says why the parity venv is excluded and what happens without it;
`pytest.ini` says why the timeout is an ini key; `jobs.py` says why monthly jobs
ride a weekly lane. That is what makes the rules survivable: a rule whose reason
is written down can be *evaluated* when it becomes inconvenient. A rule without
one gets deleted by the next person who trips over it.
