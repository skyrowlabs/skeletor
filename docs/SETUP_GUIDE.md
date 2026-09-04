# Setup Guide — Standing Up a Project Shell

**Audience: an agent.** Follow this top to bottom. It produces a repository that
governs itself from the first commit: documented conventions, a discoverable CLI,
a docs lifecycle, marker-based tests, cost-aware CI, and versioning.

The design behind every rule here is recorded in
[`DESIGN_RATIONALE.md`](DESIGN_RATIONALE.md). Read it when you want to know *why*
something is shaped this way, or when you are deciding whether to drop it.

> **The one rule this whole shell is an application of:** a rule that two files
> can express is a rule that will drift, and the copy that is wrong is always the
> one being read. Where you need a set of things checked, **discover** the set by
> pattern; do not maintain a list. Exemptions go in an allowlist **with a written
> reason** — that reason is what turns a divergence from a failure into a
> decision.
>
> **And the exemption is checked against the thing it exempts, on every run.** A
> reason makes an entry a decision; nothing keeps the decision *true*. An entry
> whose file was fixed has outlived its reason. An entry whose file left the tree
> is worse — the path can come back for something else and arrive **pre-exempted**,
> which is an exemption nobody made. A stale entry is deleted, not re-justified.

That last paragraph is newer than the rest of this guide and it was learned the
expensive way, so it is worth knowing what it cost before you treat an allowlist
as a safe place to put something.

`check_workflow_drift.py` shipped for months with an allowlist its own reader
could not parse: the keys are `<workflow>.yml:<job-id>` and the reader split each
line on the first colon, so **no entry could ever exempt any job**. Nothing could
see it. A fresh tree enrols no jobs and ships an empty allowlist, so the check is
green and stays green — the bug waits for the first person with a real divergence
to record, who finds the check will not go quiet and reasonably deletes the check.
An escape hatch that cannot be used is worse than none, because it looks like one.

Four allowlists ship, and they shipped four copies of that reader. That is how a
shared format actually fails: each copy is correct about the keys its own caller
happens to use, and nothing compares them. `scripts/allowlist.py` owns the
reading now, and `bin/skeletor-verify` **discovers** `*_allowlist.yaml` rather
than listing them — planting a meaningless entry in each and requiring the tree's
own gates to go red. That gate exists because the first attempt at this rule was
itself a list: two allowlists got a staleness check because they were the two in
front of the author, and the two missed were the two nothing would complain about.

---

## Step 0 — Decide five things (ask, don't guess)

Four of these are cosmetic and one is not. Ask the user; do not infer.

| Decision           | Default     | Why it matters                                              |
| ------------------ | ----------- | ------------------------------------------------------------ |
| **Tier**           | `core`      | The one real decision — see [`TIERS.md`](TIERS.md)          |
| CLI name           | from slug   | Becomes `./<name>`; short, lowercase, memorable              |
| Base branch        | `develop`   | `develop` if you want a release branch; `main` if not        |
| Language           | `python`    | Decides which lint overlay ships                             |
| Line length        | `120`       | 88/100/120/127 — pick one and never discuss it again         |

**On the tier**: pick the one you will maintain, not the one that looks most
thorough. An unmaintained gate is worse than an absent one — it is red for
reasons nobody remembers, so people learn to expect red, and a real failure then
looks exactly like the noise.

**On the base branch**: `develop` + `main` gives you a release branch that only
ever receives reviewed, green code, and a place for the "is it shippable" gate to
live. A single `main` is simpler and fine for a project with no release cadence.
If in doubt, take the two-branch model — collapsing it later is easy, adding it
later means retraining every habit.

---

## Step 1 — Scaffold

```bash
bin/skeletor-new ../<target-dir> \
  --name "Human Name" \
  --slug my-project \
  --cli mp \
  --tagline "One line: what this project is." \
  --tier core \
  --language python \
  --base-branch develop \
  --release-branch main \
  --python 3.12 \
  --line-length 120 \
  --org my-github-org
```

For `--tier agentic`, also pass `--timezone America/Chicago` (or wherever the
crontab will actually fire). **Never leave this implicit** — a bare
`datetime.now()` is local on your host and **UTC** on a CI runner, and that
single difference has shipped a test file that passed locally and failed in CI
for thirteen hours every Saturday.

The scaffolder substitutes every placeholder, generates the docs indexes, and
installs the merge driver, so the tree's own gates are green on the first run.

**Verify immediately.** A scaffold whose first check is red teaches that red is
normal:

```bash
cd ../<target-dir>
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
./mp --help
./mp check docs      # must be all-green
./mp test unit       # must be all-green
```

---

## Step 2 — Install the hooks and the merge driver

```bash
.venv/bin/pre-commit install --install-hooks
.venv/bin/python scripts/git/install_merge_drivers.py
./mp check merge-drivers
```

Both live **outside** version control, which is why they need a step. The merge
driver in particular: `.gitattributes` routes the generated docs artifacts
through a driver named `regen-docs`, but its *definition* lives in `.git/config`.
Without it, git falls back to a three-way text merge of a generated JSON — and a
hand-resolved conflict inside a file nobody reviews is how a branch's doc edits
get silently reverted.

---

## Step 3 — Fill in the SCAFFOLD markers

```bash
grep -rn "SCAFFOLD" --include='*.md' --include='*.yml' --include='*.py' .
```

These are the parts only the project's author can write. Do them **now**, while
the tree is small:

| Marker in                        | What to write                                              |
| -------------------------------- | ----------------------------------------------------------- |
| `CLAUDE.md` § Services           | The real components, their ports, what each is for          |
| `CLAUDE.md` § Critical Rules     | Replace the generic rules with this project's real ones     |
| `docs/ARCHITECTURE.md`           | The one diagram, and the patterns a change can break silently |
| `.github/DOCS_INDEX.md`          | A routing row per doc, as docs are written                  |
| `.github/workflows/ci.yml`       | How the integration job stands the stack up                 |
| `cli/check.py::health`           | The project's real health probes                            |
| `docs/reports/regular/README.md` | A row per scheduled report (agentic tier)                    |

### Writing Critical Rules that survive

The shipped rules are placeholders. Replace them with rules that are true of
**this** project, and follow the two properties that make the source repo's rules
survive contact with people who find them inconvenient:

1. **Each rule states what goes wrong without it**, concretely. Not "keep the
   compose files in sync" but "three tests failed every run for two days, in a
   job nobody read, because one file gained a step the other did not."
2. **Each rule is enforced by something, or is explicitly advisory.** A rule with
   neither is decoration, and the first person under time pressure deletes it.

Write the reason next to the rule in the config file too — `.flake8` saying why
an exclusion exists, `pytest.ini` saying why the timeout is an ini key. A rule
whose reason is written down can be *evaluated* when it becomes inconvenient. A
rule without one gets deleted by whoever trips over it.

---

## Step 4 — First commit and branch protection

```bash
git add -A
git commit -m "chore: scaffold the project shell"
gh repo create <org>/<slug> --private --source=. --push
git switch -c develop && git push -u origin develop
```

Then set branch protection. **The rules here are counter-intuitive and cost real
money if you get them backwards:**

```bash
# The integration branch: the contexts that must gate, even when they skip.
gh api -X PUT repos/<org>/<slug>/branches/develop/protection \
  -f 'required_status_checks[strict]=false' \
  -f 'required_status_checks[contexts][]=CI Gate' \
  -f 'required_status_checks[contexts][]=Unit Tests (host-side)' \
  -f 'required_status_checks[contexts][]=Integration Tests' \
  -F 'enforce_admins=false' -F 'restrictions=null' \
  -F 'required_pull_request_reviews=null'
```

- **Require every context that must gate, including ones that usually skip.** A
  required context satisfied by a `skipped` report costs nothing and blocks
  nothing — but it is what makes the job gate on the runs where it *does*
  execute. Trimming the list to "save minutes" saves nothing and breaks the
  Dependabot path.
- **`strict: false` on the integration branch.** "Require branches to be up to
  date" means every merge invalidates every other open PR, so a queue of N PRs
  costs N re-runs and drains one at a time.
- **`strict: true` on the release branch**, where the release PR genuinely must
  be current.
- **`enforce_admins: false` on the release branch**, so a human can merge the
  release PR by hand. That step is deliberately not automated.

---

## Step 5 — Write the first plan

Do this even if the first task is small. It is how the lifecycle gets learned
while there is nothing at stake.

```bash
cp docs/TODO/_TEMPLATE.md docs/TODO/<slug>.md
# edit: title, status, priority, phases, acceptance
./mp docs index
./mp docs status
```

Four fields decide how a plan behaves, and three of them are **never inferred**:

- **`shelf_status`** — why it is unfinished. Inferred as a backfill; an explicit
  `> **Shelf-Status**:` line always wins.
- **`Blocked-On`** — what would unblock it. **Never inferred**: a mis-guessed
  gate files a plan under a session nobody will hold, which is worse than an
  honest `unclassified`.
- **`Queue-Order`** — what gets built first, on `ready` plans only. **Never
  inferred**, lower runs earlier, gaps of 10. An unnumbered plan sorts *last*
  whatever its priority — absence is not a choice.
- **`Review-PR`** — set when the plan goes out for review. **Never inferred**: a
  guessed PR number sends a reviewer to the wrong diff.

When the plan is done, **file it**:

```bash
./mp docs file <slug> --category <category>
./mp check doc-refs && ./mp check doc-links
```

Filing is the step this whole lifecycle exists for, and it is also the step that
silently breaks links in two directions: every relative link *inside* the moved
plan, and every link elsewhere that pointed at its old path. **Repoint, never
delete** — those links are prose recording why the code is shaped the way it is.

---

## Step 6 — Write the first test, and set the baselines

```python
# tests/test_<thing>.py
import pytest

pytestmark = [pytest.mark.unit]   # this line IS the registration
```

There is nothing else to update — no CI step, no runner case, no CLI entry.
`tests/test_marker_coverage.py` fails if a file declares none.

For an integration test, gate the environment with `require_or_skip`, never
`pytest.skip`. It skips locally and **fails** under CI, because CI guarantees the
environment — and a harness that silently skips its whole suite reports green,
which is the most expensive failure mode a test suite has.

Then set the ratchets honestly:

```bash
./mp test unit
python scripts/check_skip_budget.py --suite unit --update
python scripts/check_coverage_budget.py --suite unit --update
```

Both are **ratchets, not targets**. Never chase the coverage number: a test
written to move a percentage covers the lines that were cheapest to reach, which
are the lines least likely to be wrong.

---

## Step 7 — Learn the PR loop before it costs anything

```bash
git switch -c feat/<slug> develop
# ...work; commit per logical unit...
./mp check pre-push
gh pr create --draft --base develop
# ...iterate; a draft runs the gate job alone...
gh pr ready <n>            # once, when you believe it is green
gh pr ready --undo <n>     # back to draft before pushing a fix
```

This is the single largest saving available, and it is a habit rather than a
config. A `synchronize` event on a **ready** PR re-runs everything that PR earns;
in the window the source repo measured, every PR was opened ready, the integration
suite re-ran four to six times per PR, and **42% of all Actions minutes ended in
a failed or cancelled run**.

Nothing is un-gated by drafting: GitHub blocks merging a draft regardless, and
`ready_for_review` fires the full set before it can merge.

---

## Step 8 (agentic tier only) — Turn on exactly one job

Do **not** install the whole grid. Start with one, run it for a month, and add a
second only once the first has been useful.

1. Create the heartbeat monitor and put its push URL in `.env`
   (`HEARTBEAT_REPO_REPORT=`). A job with no monitor behind it can stop running
   silently, which is the failure mode the whole system exists to remove.
2. Seed the report file it writes and add its filename to `ANCHORED_REPORTS` in
   `scripts/docs/release_window.py`.
3. Install the crontab **from the registry**, never by hand:

```bash
./mp report cron --print | crontab -
./mp report cron --check     # registered is not installed — this is what tells you which
```

4. Watch it: `./mp report watch`.

When adding a job later, follow `docs/AGENTIC_AUTOMATION.md` § Adding a job. Five
of its six steps are enforced by `tests/test_reporting_jobs.py`; only the crontab
install is not, because this repo cannot see that host.

**Decide `fix_policy` explicitly.** It defaults to `none` on purpose: a job added
without thinking about blast radius gets no autonomy rather than inheriting
whatever the entry above it had.

---

## Adopting this into an existing repository

The shell assumes a green tree. An existing repo is not green, and the failure
mode is predictable: every gate is red on day one, people learn to ignore them,
and the adoption has made things worse.

Do it in this order, one commit each:

1. **Scaffold into the existing tree** with `--force`, then review the
   diff file by file. Keep your own `README.md`, `.gitignore` and CI if they are
   better; take the rules, the docs pipeline and the CLI.
2. **Baseline every ratchet at what you inherited**, not at zero:
   ```bash
   python scripts/check_doc_links.py --update-baseline
   python scripts/check_skip_budget.py --suite unit --update
   python scripts/check_coverage_budget.py --suite unit --update
   ```
   A ratchet that starts red is a ratchet that gets switched off.

   **Allowlists are not baselined the same way.** An adoption is where most of a
   repo's allowlist entries get written, in a hurry, to make an inherited tree go
   green — and each one is checked against what it exempts from then on. That is
   the point: an entry added today to get past an inherited mess reports itself
   the day somebody fixes the mess, and is then deleted rather than re-justified.
   Write the reason for a reader who will meet it once, at that moment.
3. **Backfill the docs lifecycle**: move existing plan-shaped documents into
   `docs/TODO/` or `docs/implementations/`, run `./mp docs index`, then classify
   the gates by hand. Expect the `blocked_on` pass to be the slow part — that is
   the work, not overhead: it is the first time anyone has written down what each
   parked thing is waiting for.
4. **Adopt conventional commits going forward only.** Do not rewrite history.
   Release Please reads from the first tag it finds; set `VERSION` and the
   manifest to your current version and let it take over from there.
5. **Add the CI gate job last**, once the local gates are green. Land it as a
   non-required check for a week, then require it.

---

## Verification checklist

Before calling the setup done:

```bash
./mp --help                  # every group registers
./mp check docs              # 5/5 green
./mp test unit               # green
./mp docs index --check      # no staleness
./mp check merge-drivers     # driver installed
git log --oneline -1         # conventional subject, one line
grep -rn SCAFFOLD --include='*.md' .   # every marker resolved or deliberately left
```

Then answer these in one sentence each. If any answer is "I'd have to look":

| Question                                            | Where the answer should live      |
| --------------------------------------------------- | --------------------------------- |
| What is this project?                               | `CLAUDE.md` first line            |
| What should an agent read before touching X?        | `.github/DOCS_INDEX.md`           |
| What is unfinished, and what is it waiting on?      | `./mp docs status`                |
| What gets built next?                               | The `Queue-Order` on `ready` plans |
| Why is this rule here?                              | The line under the rule           |
| What does CI run for this PR, and what does it cost? | `docs/DEVELOPMENT.md` § CI/CD     |

---

## The failure modes this shell exists to prevent

Keep these in view. Each one is invisible while it is happening, which is why
each has a mechanism rather than a convention.

| Failure                                          | The mechanism                                    |
| ------------------------------------------------ | ------------------------------------------------ |
| Rebuilding something already built and parked    | `docs/todo_index.json`, read before building      |
| A decision re-litigated every six months         | `## Dropped, and why` in every plan               |
| Docs that describe a system that no longer exists | Link/ref checkers + the doc-table gate           |
| A green suite that stopped testing anything      | `require_or_skip` + the skip ratchet             |
| A queue whose published order is not its real order | One imported sort key                          |
| CI bills that scale with iteration, not with work | Draft-PR discipline + job-level gating          |
| A dependency bump that merges untested           | Dependabot exempt from gating + required context |
| One agent deleting another's uncommitted work    | `<cli> commit`, tree locks, worktrees            |
| A scheduled job that quietly stopped running     | A heartbeat per job + `cron --check`             |
| A job that graded the wrong branch and said green | Refuse, don't warn — decline and record why     |
