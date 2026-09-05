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

The cleanest demonstration of the difference arrived by accident.
`tests/test_docs_name_real_commands.py` was written from a bug report about one
line in one file — a setup guide naming a command the CLI never had. Two
commits later a new `docs/reports/README.md` landed, carrying three commands in
a shell block, and **the gate covered it the moment it existed.** Nobody pointed
it at the new file, and there was no list to add it to.

A registry would have been correct on the day it was written and silent on that
file, which is the failure mode exactly: not wrong, just not looking. The
difference between a check and an allowlist is only visible on the input nobody
anticipated, so it is worth recording the one time you get to watch it happen.

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

### The archive strip: a fix that went into the derived artifact

proto.pilot filed its first plan and watched it sit in `docs/implementations/`
for two days saying `shelf_status: in-progress` with all six phases and every
acceptance box ticked. Every gate was green the whole time, in both repos.

Three separate things had to be true for that, and each is worth keeping:

**The branch that fixes it was unreachable.** `add_frontmatter.py` skipped any
doc that already had frontmatter — correct for a backfill — and shared that
guard with the archive branch, which is not a backfill but the normalisation a
filing performs. A doc being filed *always* has frontmatter, so the archive
branch had never run once, in any tree ever scaffolded from this shell. The tell
was visible in every archived document: the fields that branch *adds* —
`category`, `completed`, `agent_value` — were missing too, and nobody read that
absence as a symptom.

**The fix had already been made, in the wrong place.** `gen_impl_index.py` pops
the same three fields when it builds, with a comment saying exactly why: *"a
stale `shelf_status: ready` in the archive is actively misleading."* So the
problem was known, understood, and answered — in the **derived artifact**. The
index rendered clean, `regen.py --check` stayed green, and the document went on
lying. A generated file declining to publish a field is not a fix for the field
being wrong; it is what stops anyone finding out. The gate can only go red on
what it renders, so patching the renderer is the one repair guaranteed to be
invisible.

**And the value had two homes with an override between them.** Header lines beat
frontmatter by design here — that is the whole point of them, so a human can
correct a heuristic. Which means stripping the frontmatter alone fixes nothing:
`Plan.shelf_status` reads the header first, and the plan goes on reporting its
old shelf. **When a value has a precedence chain, a change to the lower copy is
not a change.** Both forms go, and they go in `docs file` — the one
deliberate moment that knows the plan has left the tank — rather than in the
backfill, which runs on every `docs index` and has no business rewriting prose.

What holds it now is two assertions rather than one, because either alone passes
while the bug is live. The end-to-end sits in `test_docs_lifecycle.py`, which
had been *driving this exact scenario since the day it was written* — its fixture
carries both forms, it files the plan, and it then asserted on the index slugs
and never looked at the document. The nearest test to a defect is not the same
thing as a test for it.

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

### One allowlist, two consumers: a collision, not a gap

`scripts/output_allowlist.yaml` exempts a script from the output discipline, and
`_stale()` deletes an entry whose script now passes the check. That is the right
rule and it has exactly one consumer's question baked into it.

There are two. `check_output_discipline.py` asks about the **source shape** —
does this script declare `--json`? `tests/test_output_contract.py` asks about
**runtime behaviour** — does it actually answer, on this host, with something a
parser can read. jam.sense adopted the component and hit the second: a checker
that imports from a container-only mount, correct in their stack, red on a bare
runner. The natural fix was structurally unavailable, and the reason is the
interesting part — their checker *does* declare `--json`, so the source check
passes, so any allowlist entry they added would be reported stale and deleted,
and deleting it re-breaks the behavioural test. **One filename, two questions,
and validation keyed to only one of them.**

A third file would have been the obvious answer and the wrong one — it is the
same shape one layer along, and the second consumer's staleness question is not
about a path at all. The exemption is a constant in the script instead:

```python
CANNOT_RUN_ON_HOST = "imports from the container mount; needs the repo at /app"
```

Three properties, and each was a separate decision. It **travels with the
script**, so there is no path string to maintain and no way to exempt a file you
are not looking at. The value **is** the reason, so an exemption without one is
not expressible rather than merely discouraged. And it is **validated in the
direction that matters**: a script claiming it cannot answer `--json` here,
which then does, is reported as a stale claim — the same "checked against the
thing it exempts on every run" property the manifest has.

The generalisation is the one this session kept arriving at from different
directions: an exemption belongs at the site that needs it, holding its own
reason, checked against reality on every run. `Suite.scheduled`,
`SCAFFOLD-OPTIONAL`, and this are three spellings of it, and each was proposed
by the consumer who tripped over the version without it.

---

## Propagating a template change: merge cleanly or say so

A generator's second problem arrives about a year after its first. Twelve repos
have been scaffolded, skeletor has improved, and none of them have. Re-running
the scaffolder with `--force` would overwrite the half of each tree that is the
*user's* — so nobody runs it, and the improvement lands nowhere.

`bin/skeletor-upgrade` is a three-way merge, and the shape of it is the whole
argument. Eight of the 111 template files carry a `SCAFFOLD` marker and are
meant to be edited; the other 103 are machinery almost nobody touches, and the
machinery is where an improvement lives. So the common case is a clean
overwrite, and the interesting case is small.

Two rules do the work:

* **A conflict is never written.** `git merge-file` will happily emit markers.
  This does not let it: on conflict the file is left exactly as it was and the
  template's own base→ours diff goes to `tmp/upgrade/`. A conflict marker in
  somebody's `CLAUDE.md` is a broken file that *looks* like a merge, in a tree
  nobody is watching.
* **Nothing is deleted.** A file the template stopped shipping is reported. The
  same posture as `skeletor-check-pins`, which reports a bump and never makes
  one. The single exception proves the rule: a real run clears the sidecars it
  wrote into `tmp/upgrade/` on a previous run, because *not* clearing them is
  what broke the sentence that sends a reader there. That deletion is bounded to
  the two suffixes this tool writes, so a file of the user's in that directory
  survives, and its count is printed.

### A correct sentence and a correct directory, disagreeing

The conflict and collision reports are the only place this tool tells a reader
to go **open a file**, and both sentences shipped unconditional. Under
`--dry-run` the tool printed "what the template changed in each is in
`tmp/upgrade/<path>.patch`" and wrote nothing there. Separately, a real run
wrote today's sidecars beside every earlier run's and cleared nothing. Each
behaviour is defensible alone — a dry run *should* write nothing, and deleting
from somebody's tree is what this whole tool refuses. Together they produce a
directory that is a superset of a plan that no longer exists, described by a
sentence asserting it is the plan just printed. A stale patch and a fresh one
look identical at the moment somebody is trusting one.

Nothing inside this repository could see it. Both halves are correct to their
writer; the defect is entirely in what a *reader* does with them, and it took an
outside consumer standing in front of a four-day-old `ci.yml.patch` to notice.
That is the same class the workspace guide states for cross-repo seams — a
writer and a reader inside one head agree with each other by construction.

The general form is worth more than the fix: **an instruction naming a path is a
claim about that path's contents, and the two are maintained in different
places.** Wherever output says "look in X", something has to keep X true — which
here means the tool either writes X, or says it did not.

### The category with no evidence behind it

An upgrade classifies from the manifest: an entry with a different hash is an
edit, no entry at all is a collision. **A genuinely new file has neither**, so
it is added, and that is the one verdict backed by nothing.

Usually right, and there is one case where it is reliably wrong — which the
report-and-adopt loop *manufactures*. The sequence that produces a good template
change is: a consumer hits a hole, writes the gate **in their tree** to close
it, reports the idea, and this repository implements it at the path it would
have chosen anyway. Both halves are correct. The paths differ for no reason but
that they were picked independently, and the upgrade then reports as a clean
addition a file that leaves the consumer running one gate twice, under two
names, in two files that will drift.

It happened the first time it could: `tests/test_pyright_scope.py` shipped here
from proto.pilot's report, and their `test_lint_tool_parity.py` already held the
same gate — not merely similar, the same precondition argued the same way, both
docstrings quoting the same sentence about matchers.

No manifest can catch it. `cross_check` compares paths and hashes, and this
needs a diff of *purposes*. So the remedy is not in the tool, and it is cheap
because the missing fact is already in hand: the docstring says who reported it.
**When a gate ships from a report, tell the reporter the path it shipped at** —
one line in a message being sent anyway. Then they delete theirs before
upgrading, or keep theirs and skip ours, and either way it is a decision instead
of a silent accretion.

That version depended on a message being remembered, and it was not: the same
duplicate arrived on proto.pilot's next dry run, unchanged, and they had to
report it a second time. So the line now lives **in the file that ships**, under
a heading addressed to the reporter — `tests/test_pyright_scope.py` says what to
do if you already hold this gate. A file carries itself into every tree that
takes it, including trees whose owner never saw the message; a message is a copy
of the fact in a place nothing revalidates, which is the failure this repository
names everywhere else and had reintroduced as a courtesy.

The adjacent hazard is the same fact one step later. `test_docs_name_live_code.py`
came from proto.pilot and `test_docs_name_real_commands.py` was written here
afterwards; they now sit side by side with names one word apart, sharing a
scoping rule and nothing else — one asks git about a removed *callable*, the
other asks the click registry about a *command* somebody is told to run. That is
the shape somebody eventually de-duplicates by reading the filenames, and the
survivor silently stops asking one of the two questions. Each docstring now says
the other is not a copy of it, in both directions, because whoever is tidying is
reading whichever one they opened.

Worth stating as a general shape rather than a courtesy: a producer that adopts
consumer ideas will hand back duplicates of them, and only the producer knows
which of its files came from whom.

### The loop's own failure mode: a number with a story attached

The exchange that produced most of this document also produced the way it goes
wrong, and it is not disagreement. It is **agreement neither side checked**.

jam.sense offered a `tree_lock.py` backport as "185 lines against 896", listing
five behaviours their version had. Four of the five were already here. They had
reasoned from their own shape — *they lack our machinery, so they lack the
property* — and I accepted the capability gap without challenging it, with
`Hold.alive`, `sweep()` and the fail-closed `would_strand` open in front of me.
Refuting it took two minutes and neither of us spent them.

The tell is worth naming because it is cheap to check and neither party sees it
from inside: **a measurement that arrives with a narrative attached gets
believed.** 185-against-896 is a real number, the five behaviours were real
behaviours, and the story joining them — *a mature repo has learned things a
seed has not* — is true often enough to pass. What broke it was not more
reasoning on either side. It was a third kind of act: sitting down to write the
patch, which forces a read of the thing being patched.

Two corollaries this repository already half-held, now stated together:

* **A fix in a mature repo is a repair to that repo's choices at least as often
  as it is an improvement.** jam.sense's `Hold.root` field claws back an
  over-reach they chose — one lock directory per repository rather than per
  checkout — and is dead weight for a design that never took the over-reach.
  Offering it as an improvement inverts the burden of proof; the honest form is
  *"here is the choice we made and the bill it came with"*.
* **A withdrawn offer is not wasted.** The one that was withdrawn found a live
  defect in both repos — `worktree drop` deciding the fate of a checkout it
  never asked about — three functions from anything either side was looking at,
  reachable only because checking the offer meant checking what a second
  checkout actually does. The offers are the mechanism, not the overhead.

The part worth stealing is how the manifest handles its one derived value. The
base is reproduced by re-rendering, which needs the generator's git history —
and there are ordinary reasons that is absent: a `--depth 1` clone, a tarball, a
collected ref. So the manifest also carries a hash per file, purely as a
fallback, and that is a cache of something the render already answers. Normally
this project would refuse it: the failure mode of a stale cache is silent.

It is allowed on two conditions, and they generalise:

* **It is checked against its source on every run that does not need it.** When
  the base *is* rendered, it is re-hashed and a disagreement is a hard failure.
  The one run that depends on the cache is never the first to test it.
* **What it proves is exact, not probable.** An equal hash means the file *is*
  byte-for-byte what the generator produced, so replacing it cannot lose an edit
  that was never made. The fallback is allowed to write files because of that,
  and it is allowed to merge nothing, because merging needs the base text.

The subtle half is which bytes get hashed. The recorded hash is of **what the
generator produces**, never of what is on disk — a merged file is neither the
old render nor the new one, so hashing the tree would record it as pristine and
the next upgrade would overwrite the merge.

---

## Vendor tooling: segment by kind, never by vendor

The shell was built against one agent, and sixteen of its 111 files carried that
vendor's name. The obvious move is to put all sixteen behind a flag. It is the
wrong one, and the reason generalises past agents.

Those sixteen files were two unrelated things:

| | Files | Auto-loaded by the tool? |
| --- | --- | --- |
| The conventions — commits, docs, testing, output, language rules | 8 | **No.** Nothing loaded them. They were read because the root instruction file *named* them |
| The tooling — settings, hooks, subagents, skills | 7 | **Yes.** Real product features with no equivalent shape elsewhere |

The rules had never been vendor-anything. They sat in a vendor directory by
habit, and the directory name was a claim that was never true. Two consequences,
both real:

* **Segmenting by vendor puts the testing rules behind the flag.** `--agent none`
  would have shipped a project with no testing conventions — a worse tree, sold
  as a more portable one.
* **Neutral documents depended on a vendor path.** `docs/DEVELOPMENT.md`,
  `docs/README.md` and `.github/CONTRIBUTING.md` all linked into it, and so did
  a *generated* `docs/TODO/README.md` — the generator recreated the dead link on
  every run. Deleting the vendor directory broke the tree's own `check docs`.

So the seam is **content versus tooling**, and it costs almost nothing to cut
there: the rules moved to `docs/rules/`, and the vendor overlay holds only the
seven files that are genuinely that product's.

The part worth stealing is the test. "Separable" was an assumption for as long
as nobody tried it, and it was false. `bin/skeletor-verify` now scaffolds with
the vendor overlay off and asserts three things — no vendor directory anywhere,
all the rule files still present, and the tree still passing its own gates. The
middle one matters most: without it, the cheapest way to make the first two pass
is to drop the conventions along with the tooling.

---

## An extension point with no extensions

The scheduled-jobs layer splits every job into deterministic collection and an
agentic triage stage, so exactly one line of it was ever tied to a vendor: the
subprocess call that runs the agent.

The tempting fix is a table of adapters — Claude, Codex, Cursor, Aider — and it
is the wrong one, for a reason worth generalising. **Nothing in this repository
can test any of them.** Three untested code paths would ship, and the failure
they produce is the worst-shaped one available: unattended, at 03:15, in a job
nobody is watching.

Specifically, the run ledger's central rail is *a job whose agent never ran must
not report `ok`*, and it rests entirely on `returncode == 0`. Agents disagree
about that contract — some exit 0 having refused the task. An adapter that gets
it wrong does not fail; it reports success for work that never happened, which
is precisely the condition the ledger exists to make impossible.

So what shipped is the seam and the contract, not the adapters: one argv
template, overridable, defaulting to the tested invocation, with the contract
written where somebody adding an adapter will read it. The template is refused
if it lacks the prompt token — an agent invoked with no instruction starts, does
nothing, and exits 0, which is the failure that looks most like success.

The general form: **when you cannot test the alternatives, ship the seam and the
contract, not the alternatives.** A configuration point with one tested value is
honest. A registry of untested ones is a promise the code cannot keep.

---

## Test the surface people actually type

A suite can be large and still leave the one thing every user touches unproven.
This shell had 43 tests and **none of them executed a CLI command** — every one
checked a module or a config file. The commands were verified by somebody having
run them once, by hand, at some point.

Two bugs of that exact shape had already shipped: a helper that joined its first
argument onto the project root made `check pre-push` — the first command the
scaffolder prints — impossible to pass at any tier; and a `--fix` flag the CLI
advertised and forwarded had never been defined by the script receiving it, so
it exited 2 on "unrecognized arguments" for as long as nobody typed it.

The first is caught by running commands. **The second is not**, and that is the
more interesting half: a smoke run passes no flags, so it exercises exactly the
path that already worked. Catching it needs the forwarded flags checked against
the script that receives them — a contract between two source files, invisible
to both.

Three things worth stealing from how it went:

* **Enrol by walking, not by listing.** The command tree is walked, so a new
  command is covered by existing. What must not run — anything that invokes an
  agent, anything that mutates, the suites themselves — is exempt with a written
  reason. Agent-backed commands are exempt from the *job registry* rather than
  the allowlist, because they are generated from it and a per-job exemption
  would be a second registry.
* **A scan that matches nothing is a test that always passes.** The first
  version of the flag check compared the flag against the script's `--help`
  output, and passed against a deliberately reintroduced bug — because the
  script's *docstring* mentions the flag and argparse prints it as the
  description. The bug was only visible because the check was tested by breaking
  the code it protects.
* **A test that mutates works on a disposable copy.** The lifecycle test copies
  the tooling into a temporary directory and operates there. That is only
  possible because every path derives from the location of the package, which
  was a refactor done for unrelated reasons and paid for itself here.

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

### The other half of a marker, which took a consumer to see

Marker-based registration is the strongest pattern here and it has an edge that
went unstated for as long as the tree was headless. A marker is how a test file
joins a suite. It is also, and by exactly the same act, **how a test file leaves
CI** — and only one of those is visible:

> **Marking a test with a marker no workflow selects deletes it from CI.** The
> unit job runs `-m unit` and deselects it, nothing else selects it, and every
> check reports green over a smaller set. Nothing is red at any point, and no
> output anywhere distinguishes the smaller set from the whole one.

That shipped. A `ui` suite was added — a row in `cli/test_cmds.py`, a CLI
command, a documented description, a considered empty-suite message — and no job
in `.github/workflows/` ran `-m ui`. Everything about the zero case was right and
the populated case was a hole.

proto.pilot found it from the outside, which is the only place it was visible:
they hold 36 Textual pilot tests matching the marker's own description word for
word, so adopting it as documented would have dropped all 36 from every run they
do. They kept the tests on `unit` instead, which is correct and means the marker
was unusable for them as written. **A registry row that costs coverage to use is
worse than an absent feature**, because the absent one does not invite anybody.

Two fixes were available and only one is honest. Calling `ui` a suite CI cannot
run is false for at least one of the three stacks the description names — a
Textual pilot is headless and runs on a bare runner — so the answer is the job.
A browser or an Electron window may still need a driver or a virtual display,
and that setup belongs to the adopting repo: a job failing loudly for want of a
display is strictly better than tests quietly leaving CI.

The generalisable part is not the job, it is where the obligation lives.
`Suite.scheduled` is a field on the row, defaulting to `True`, so the safe answer
is the one you get by not thinking about it, and `tests/test_ci_runs_every_suite.py`
turns the unsafe answer into something you have to write down. Two literals
collapsed into it on the way — `{{CLI}} test all` had been excluding `manual` by
name, which is the same question CI asks, written twice.

It also cost `bin/skeletor-verify` a list. Its empty-suite gate named
`integration` for as long as that was the only tolerant suite; `ui` arrived,
took the identical code path, and the gate would not have noticed either way.
It discovers the set from the tree's own registry now — and fails on an empty
one, because a loop over nothing passes every assertion inside it.

#### The exemption had the same shape as the bug

The fix shipped and proto.pilot took it the same day — and took the exemption,
which is the option the fix invented and therefore the least exercised half of
it. Nothing in their tree is marked `ui`, so `scheduled=False` and delete the
job, exactly as documented. Two things were wrong with that path.

**The template made the documented act break the workflow.** `release-please`
shipped `needs: [lint, unit-tests, integration, ui]`, so removing the job left a
dangling reference — and GitHub validates the job graph *before* scheduling, so
that is not a red job. It is a `startup_failure`: zero jobs, no logs,
`gh run view --log-failed` answering "log not found", and nothing on the commit
naming the line. Every local gate was green, because about a suite with no
marker and no job the registry and the workflows agree perfectly.

`actionlint` catches it, and could not have helped: it runs in skeletor's
verifier against what skeletor ships, where the job is still there. **The
failure happens in a tree that has edited the file**, which is the one place
only the shipped checks can reach. `tests/test_workflow_job_graph.py` is the
answer, and it generalises past this case — removing a job is ordinary, and the
reference that outlives it is never in the block you edited. It also covers
`needs.<job>` in an `if:`, where the same mistake is quieter: an unknown context
is not an error, it is null, so the condition is false, the job is skipped, and
branch protection accepts a skipped required check.

**And `scheduled=False` was two claims wearing one spelling.** `manual` is
unscheduled because it *cannot* run unattended, which stays true however many
tests it gains. proto.pilot's `ui` was unscheduled because the suite was
*empty* — a fact about contents, and contents change. Mark one test and the row
is false with no edit to it, no workflow change, and nothing red anywhere: the
original bug, reintroduced under its own exemption and therefore past the gate
built to catch it.

So the reason is data. `UNSCHEDULED` has two entries, a row must name one, and
naming `empty` implies an emptiness assertion that the suite writes from the
registry — free in a tree that made no such claim, which is every fresh
scaffold. It is the `ships_tests`/`scheduled` split again on a third pair of
questions, and the tell was the same: **a flag that has never been observed to
disagree with another flag is undistinguished, not confirmed.** Three rows are
not enough to tell two booleans apart; the fourth row is where the coincidence
shows.

Ground truth is pytest's own collection, not a scan for `pytestmark`. A single
`@pytest.mark.ui` on one function is invisible to a source scan and perfectly
visible to the runner — and it is exactly what somebody writes on the day the
exemption stops being true.

### Two bugs that hid each other, and only one of them was a bug about tests

stash.flow reported this pair on v0.5.1, and the order matters: the visible one
was in a test, the one worth generalising was in the check that should have
caught it.

`test_a_host_exemption_is_still_true` parametrized over the checkers declaring
`CANNOT_RUN_ON_HOST`. Zero of those is the *intended* state of a fresh scaffold
and the docstring said so approvingly — "it costs nothing until somebody makes
the claim". It does not cost nothing. **pytest reports an empty parameter set by
skipping**, `tests/skip_budget.json` ships `max_skipped: 0`, and so every tree
generated at v0.5.1 was born one skip over its own ratchet. The intended case
was the breaching case.

Two things are worth separating there. An assertion that is *correct* when empty
and a *skip* emitted when empty are different objects, and a ratchet counting
skips can only see the second — which is why this survived a suite that already
holds the "negative over an empty set" rule in four places. And the reason the
empty case is safe at all is structural rather than a guard: `_host_exempt()`
and `_host_runnable()` partition the checkers, so an exemption the scanner fails
to see does not disappear, it lands in the other set and fails loudly against a
script that cannot answer `--json`. The fix is a loop instead of a parametrize;
the emptiness needed no new assertion.

It reached users because the ratchet was not running. `ci.yml` ran
`python -m pytest tests/ -m unit -q --durations=25` — no `--junitxml` — and then
`python scripts/check_skip_budget.py`, which found no report at `tmp/junit.xml`,
printed a warning and **exited 0**. Every push, every scaffold, since the
template first shipped. The check that exists to catch a suite quietly stopping
testing had quietly stopped testing, and its output was a `⚠️` in a green step.

The general statement, and stash.flow's:

> **A graceful degradation that degrades into a pass is not graceful.** There is
> no case where *"I could not measure"* is the same answer as *"the budget is
> respected"*, so a checker whose whole job is to fail on a number has no
> warn-and-pass path. A ratchet with nothing to read has not passed; it has not
> run.

`check_coverage_budget.py` carried the identical hole, latent — the one workflow
that runs it does write its report — and the pair is the useful reading: a
latent instance is one edited workflow away from the live one, so both were
fixed together rather than the one that had already fired.

`bin/skeletor-verify` structurally could not see this. It runs a generated
tree's gates directly, where the hand invocation is fine; the defect lived in
what the **workflow** passes, and no tree's own suite was asking. So the tree
now ships `tests/test_ci_ratchet_inputs.py`: for every workflow step running a
ratchet, the artifact that ratchet reads must be named earlier **in the same
job** — a later job is a different runner with a different filesystem. Enrolment
is by pattern at both ends, so the next ratchet is covered by existing: a ratchet
is any `scripts/check_*.py` naming a file under `tmp/`, read from its source.

Both plants were run and both went red, including the one that matters most
here: replacing the flag with `# TODO: restore --junitxml=tmp/junit.xml here`
leaves the string in the file and the job without the flag, so an unmasked grep
passes. That is `scripts/yaml_text.py`'s rule collecting its third instance —
a check hunting for a *requirement* must mask comments, because the string most
likely to appear where the thing is missing is a comment saying it should be
there.

The nightly then turned out to be wrong in a quieter way, found while fixing the
first two and left unfixed for a release because the remedy was a design call I
did not want to guess at. It ran `-m "unit or integration"` into one report and
checked it with `--suite unit`; `count_skips` sums a whole file, so integration's
skips were charged to the unit budget and reported under the unit suite's name.
Green in a fresh tree, because a scaffold ships no integration tests — and a
false red naming the wrong suite in any tree that grows one.

stash.flow settled it, and the argument is the one that generalises: **a
combined report is not checkable per suite at all**, so the workflow produces one
report per marker rather than the checker learning to partition one. That keeps
`count_skips` summing a whole file, which is the only thing it can be correct
about. Coverage is the mirror image and stays combined — a line rate is a
whole-tree measure both runs contribute to — so the two pytest runs append into
one data file and the xml is written in its own step, where an empty integration
selection cannot skip it. `tests/test_ci_ratchet_inputs.py` reads the report
named **on the invocation** in preference to the script's default, because
otherwise the correct workflow would have been the red one.

### Two rules that came out of this and are not about ratchets

The first is the one the empty parametrize taught, and it has to be stated with
both halves or it does damage: **when an enumeration can legitimately be empty,
ask what makes the empty case carry no information before reaching for an
assertion about it.** Here it is a partition — the exempt and runnable sets are
complements, so a missed declaration lands in the other one and fails loudly,
and a guard would add nothing. That is the *narrow* case. `tests/scanning.py` is
the wide one: most scans have no complement to fall into, so an empty result is
indistinguishable from a broken pattern and `scanned()` is what says so.

Stated one-sidedly it invites the wrong deletion, and the tree ships both rules,
so the docstring now carries the complement and names `scanning.py`. stash.flow
supplied the counter-example by applying the rule to a read-only surface pin and
getting the opposite answer: there the set not growing *is* the invariant, so
the guard is doing the work. A reader who only ever meets the partition case
will delete a guard that was load-bearing.

The second is about reporting rather than testing, and it arrived as a
near-miss. Checking the ratchet gate from their own tree, stash.flow read

    E   assert 0 <= -1

and began writing up a gate that bites correctly and explains nothing. It was
`-q` plus a `tail` cutting the message off; the full output names the workflow,
the job, the script and the artifact. They checked before sending, and the rule
is worth more than the non-bug:

> **A report about an absent explanation has to be made against unabridged
> output, because the tooling that abridges it is indistinguishable from the
> code that never wrote it.**

That is the same shape as the `wc -l` line in `skeletor-upgrade`'s collected-ID
recipe, one layer up: there, a wrong interpreter leaves `grep` writing empty
files and `diff` reporting no change, so the pipeline reports "nothing changed"
having compared nothing. Here the truncation is in the reader's own terminal.
Both are a negative claim sourced from a view that could not have shown the
positive.

### A gate that only runs in the reader's coordinate system

`docs/rules/testing.md` told every generated tree to *"use the fixtures in
`tests/fixtures.py`"*. No tier has ever shipped that file. A prescription, in a
rules file, naming a helper the reader does not have — present since the
template first existed, found by stash.flow from an adopted tree.

Three gates were in position and **each excluded it by construction**, which is
the part worth keeping. `test_docs_name_live_code.py` asks whether a doc names a
callable this tree once defined and no longer does, put to `git log`; a file
never defined is outside that question, and it is outside it because of the
decision that makes the gate allowlist-free. Its docstring argues that "every
backticked thing must resolve" has a false-positive rate that makes it useless —
which is true of **callables**, and got applied to paths by adjacency.
`check_source_doc_refs.py` runs source → doc; this is the other direction.
`check_doc_links.py` reads markdown links; this is a bare backticked path.

The measurement decided the scope, and it took three passes. A naive predicate
found sixteen dangling paths in an `agentic` tree, of which seven were the
*predicate's* error — `docs/TODO/README.md` says `../implementations/`, correct
and unresolvable against the repo root — so paths resolve against the root or
the citing document's directory. Of the nine left, five were about notation
rather than code: a git ref (`origin/develop`), an example filename in a skill,
a report a job will write, two directories the docs rules say to create on
demand. Restricting to source and config extensions removed all five at once and
kept the defect, because a document naming a document is usually naming one that
does not exist *yet* and a `.py` path has no such tense. Final ratio, on fresh
trees at three tiers: 31–38 citations each, one dangling, **no exemptions**.

The reason it ships in the template rather than living here is stash.flow's, and
it generalises past this check: **the population is only checkable in the
reader's coordinate system.** This repository's prose names shipped files the way
a scaffold sees them — `tests/scanning.py`, not `template/core/tests/scanning.py`
— because that is how the reader will meet them. Measured at this root the same
question gives nine references, none dangling, and one exemption needed for a
placeholder form; that gate was written and abandoned on those numbers. The same
predicate in a generated tree covers 38 and needs none. A check can be worth
building at one end of a boundary and not the other, and the coordinate system is
what decides.

That gate then shipped with two defects of its own, both found by stash.flow on
the first adopted tree, and both the same slip: **the parts of the sibling gate
that were argued in its docstring transferred, and the parts that were
implemented did not.** `test_docs_name_live_code.py` scopes by `git ls-files`
and excludes narrative stages by role. The new one walked the disk with `rglob`
and had no role exclusion at all — while its docstring cited that sibling three
times.

The `rglob` half is the worse one and not for the obvious reason. It read
`.venv/lib/.../pyright/dist/README.md` and `.pytest_cache/README.md` — six
documents from other people's packages, which `.gitignore` already declares are
not the repository's claim. The verdict is therefore **machine-dependent**: it
turns on what the dependency tree happens to ship, so one person's red cannot be
reproduced by the next. That is worse than a false positive everybody sees. It
passed here for a reason no better than luck — pyright's bundled README is a
large document that happens to contain no path-shaped inline code.

The role half produced the reusable rule, and it is stash.flow's: **a template
gate that scans by role needs the role set to live in a file the adopter owns,
because the roles are the part the generator cannot know.** This template ships
`docs/TODO/` and can enumerate it; it cannot know that an adopter froze their
concept work in `explore/` — 19 of their 44 tracked documents, upstream of code,
describing a codebase that has since moved. Naming files that no longer exist is
what those documents are *for*. Had the exclusion been a constant in the test,
every adopter with a frozen stage would carry a divergence the three-way merge
holds forever; read from `scripts/paths.py`, it is a one-line extension to a file
that is already theirs. `NARRATIVE` moved there, and both gates read it.

Both scoping questions now have one home in `tests/repo_files.py`, which is the
`scripts/allowlist.py` lesson arriving for the third time: the second consumer of
a rule is where a rule that lives inside its first consumer goes wrong.

### The defect that lives in what two files jointly imply

Both of the corrections above were the same shape, which stash.flow named after
the second one landed: the defect was not in either file. `tests/scanning.py`
argues that a scan must refuse to enumerate nothing.
`tests/test_output_contract.py` argued that what makes an empty enumeration safe
is the shape of the set rather than a guard beside it. **Each was true about the
case in front of its author.** They shipped four directories apart, in one
repository, for two releases, and read together the second licenses deleting the
first.

This is the workspace's rule about test suites, one level up and with no suite
involved:

> A suite cannot find a disagreement about an artifact it publishes, because
> writer and reader share an author.

Two prose claims are that with the suite removed. Nothing compares them —
`check_doc_links.py` asks whether a reference resolves, the tier-composition gate
asks whether it resolves *here*, and neither can ask whether two paragraphs
recommend opposite things. Consistency between them is assumed rather than
checked, and the author is the last person positioned to notice, because he met
each case separately and was right each time.

stash.flow's report ends "I do not have a remedy and I am not sure one exists
short of what just happened." The remedy is what just happened, and it is worth
naming as a procedure rather than an accident: **an outside case that neither
claim was written for.** Their read-only surface pin fit neither paragraph — no
partition to make the empty case safe, and the set not growing *is* the
invariant — so applying the rule produced the opposite answer and the two claims
collided. That is the same instrument the workspace prescribes for seam defects,
pointed at prose instead of bytes: run the actual consumer against the actual
producer, and the disagreement surfaces in what the consumer does with it.

Which means the practical form is a habit rather than a gate. A rule stated in
one file is checkable against the file that states the opposite rule, and
**nobody performs that check unless a second tree hands them the mismatched
case** — so the value of an adoption is not only the bugs it finds. Two of the
three defects it found here were things no test could have been written for,
because the thing that was wrong was an implication between two correct files.

There is an actionable half, and it is a rule rather than a record — so it does
not live here. `template/core/docs/rules/docs.md` owns it, under *Where a Claim
Lives*, which is the file somebody has open while writing the docstring and the
one that reaches an adopting tree. It resolves the tension that produced this
defect: *every rule carries its reason, in the file that states it* is what makes
restating a convention feel correct, and *a claim has one home* is what forbids
it.

stash.flow caught that this entry originally stated the rule here instead, in the
imperative, in a document read when deciding whether to drop a mechanism and
shipped to nobody — the same defect one turn later, and in the paragraph
prescribing against it.

One thing stash.flow did **not** do is the reason this is a template fix rather
than an adopter's workaround: they left `max_skipped: 0` alone. Raising it to 1
would have recorded a claim about their tree that was false — they had no
legitimate skip, they had our empty parametrize — and it would have outlived the
fix as a permanently loosened ratchet nobody remembers loosening. A number that
is wrong in the honest direction is worth more than a green one.

### A guarantee implemented by rendering cannot survive rendering

`docs/DEVELOPMENT.md` opened its setup section by saying the block above it "**is
rendered from** `setup_commands()` in the scaffolder — the same source as the
README's — so there is exactly one place these steps are written down". Every
clause of that was true when it was written and none of it is true in the tree
that carries it. The generator ran once, at scaffold time, and left. What a
reader has is two static blocks in two files that wrap the shared steps
differently, with nothing comparing them — which is precisely the condition the
paragraph promises has been eliminated, described in the present tense by the
sentence sitting on top of it.

stash.flow found it and named the class, and it is the sharpest thing in this
document about writing template prose:

> **A guarantee implemented by rendering cannot survive rendering.** The
> generator's single-source mechanism is spent at the moment of generation.

The tell they refined it to is narrower than "check your tense", and the
narrowness is what makes it usable: **a sentence in the present tense about an
ongoing guarantee that was actually a one-time act.** Most present-tense prose in
a generated tree is fine — `docs/rules/` describes standing conventions, and
those really do hold. The dangerous subset is the sentence that names a
*mechanism* as currently operating. `is rendered from`, `is generated by`, `stays
in sync with`, `the scaffolder installs it`. Each of those is a claim about
something happening now, sourced from something that happened once, and the
reader's remedy — go look at the generator — is unavailable to them by
construction, because the generator is in a different repository they may not
have.

Two more of the same sweep, and they are worth keeping because neither reads like
the first one:

**The scaffolder installs it; verify with `{{CLI}} check merge-drivers`.** True
for the person who ran the scaffolder, and false for every clone after theirs —
which is the whole reason that bullet exists, since the driver definition lives
in `.git/config` and `.git/config` is what a clone does not carry. So the
sentence describing the untracked-state hazard was itself written from the one
machine where the hazard cannot occur. The fix is an instruction rather than a
report: every clone after the first runs
`python scripts/git/install_merge_drivers.py` by hand, and `check merge-drivers`
checks and never installs. The `.gitattributes` comment had the same sentence in
a worse form — it prescribed a `{{CLI}} setup` that `docs/DEVELOPMENT.md`
explains in bold cannot exist, because the CLI needs the virtualenv that setup
would have created.

**"two of the four workflows this template ships."** `scripts/yaml_text.py` is a
`core` file; `core` ships three workflows and `governed` adds a fourth. The count
was measured in one tier and written into a file every tier carries. There is no
tense problem and no generator involved — it is the same failure with the axis
changed from time to space, and the same remedy: state the shape, not the count.

The ruling that came out of the sweep is a **not**, and it is recorded because
the measurement is the evidence. The `{{CLI}} setup` defect suggests a gate over
backticked command references outside markdown fences. Measured on a fresh
`agentic` tree: 29 distinct backticked invocations, **zero** dangling, and two
surviving mentions of commands that do not exist — `{{CLI}} setup` and
`{{CLI}} service`, in `AGENTS.md` and `docs/DEVELOPMENT.md`, both naming the
command precisely in order to say it is not real. Those are the convention's own
vocabulary, the category this repository already separates from a mis-shaped
predicate, and no predicate over the notation can see out of it. The structural
marker that does separate them is the one `test_docs_name_real_commands.py`
already uses — a fenced ```bash block is the difference between describing a
command and telling you to run one — and the two survivors are outside a fence by
construction rather than by exemption. Widening it to catch a comment in
`.gitattributes` would have bought one caught defect at the price of two false
positives that cannot be predicated away. The defect is fixed; the gate is not
built.


### The false clause rides on a true one

The fix above missed `AGENTS.md`, which carried the identical sentence and is the
first file an agent reads in any generated tree. stash.flow's sweep found it, and
it is a better instance than the one that got fixed, for two reasons that are
worth separating.

**It was over-claimed while the mechanism was still live.** `{{SETUP_COMMANDS}}`
renders two lines. The Quick Start block has five — `check pre-push`, `test unit`
and `check health` come from nowhere but that file. So *"**These** are rendered
from the same source as the README's Setup block"* was false about three of the
five on the day it was written, in this repository, before any generation boundary
existed to cross. The spent-guarantee failure and the over-claim are not
independent: you write the wider claim *because* the mechanism feels like it
covers the whole block, so expect them together.

**And the false clause was conjoined to a true one.** The full sentence is
*"...rendered from the same source, **and every one of them exists**."* That
second half is checkable and correct — all three commands resolve in a fresh
`agentic` tree — and it is the half the paragraph exists for, since its entire
subject is an earlier version of the file opening with `setup` and `service up`,
which the CLI never had. A reader who accepts the paragraph's own invitation to
verify runs the commands, finds them working, and banks the conjunction.

That sharpens the tell one more turn, and it is the part that goes in the
invariant:

> The dangerous form is not only a present-tense claim about a one-time act. It
> is that clause **conjoined to a verifiable one** — where confirming the
> conjunction confirms only the half that can be confirmed.

Three verbs catch the clause. Nothing catches the conjunction, and the
conjunction is what makes a false sentence survive review, because the sentence
*is* partly true and the true part is the part a careful reader tests. The fix
keeps the live clause and leads with it, so the paragraph now claims exactly what
it can support.

### The gate that cannot fail here and matters there

Removing the rendering sentence made a real gap visible: three files carry the
setup steps — `AGENTS.md`, `README.md`, `docs/DEVELOPMENT.md` — and nothing
compares them. `docs/DEVELOPMENT.md` now says out loud "nothing will tell you if
you miss one", in a tree whose own conventions say something should. stash.flow's
reading of that is right and general: **the rendering sentence was standing in
for the check.** "These come from one source" is what you write *instead of*
enrolling the pair, and it discharges the requirement by assertion. Remove it
correctly and the requirement becomes visible and unmet.

Their measurement — 3 blocks, 2 lines identical across all three, 0 exemptions,
enrolment by fenced `bash` block rather than by a notation guess — is a better
ratio than either gate declined above. And the gate still does not belong in
`bin/skeletor-verify`, for a reason neither of us had until the template was
checked: **all three files carry `{{SETUP_COMMANDS}}`.** One `re.sub` substitutes
one string into three places, so upstream those lines cannot disagree. A gate
here would be asserting that a regex substituted the same value three times — it
cannot go red, which is the one thing this repository refuses to ship.

In an adopted tree the placeholder is gone, the three blocks are static text, and
drift is not only possible but permanent. So the check belongs in the template, as
a test the tree runs on itself.

This is the coordinate-system rule on its other face. The path gate was worth
building in the reader's tree because the *population* is larger there — 38
citations against nine. This one is worth building there because the *failure
mode does not exist here at all*. Same conclusion, and it would be easy to
generalise the first argument into "measure at the far end", which would be
wrong: the question is where the thing can go wrong, and volume is only one
symptom of that.

It also retires the sentence that prompted it. Once the tree checks its own setup
blocks, `docs/DEVELOPMENT.md` stops saying "nothing will tell you if you miss one"
and names the test — which is a present-tense mechanism claim that is *true in the
reader's tree*, because the mechanism ships with the prose and runs beside it.
That is the honest half of invariant 7, and the contrast worth keeping: a claim
about CI, made by a file CI runs, is checkable by the reader; a claim about a
generator that has left is not.


### A flag that reads as symmetric, and one language that shipped unrunnable

Building the drift check above found a worse bug than the drift it was for.

`--language` offers `python`, `node` and `both`, and `setup_commands()` treated
them as three symmetric choices: the venv-and-pre-commit steps were guarded by
`language in ("python", "both")`, the `npm install` step by `language in ("node",
"both")`. It reads as obviously correct. It is not, and the reason is one
directory level away from the function: `cli/`, `tests/` and `scripts/` all ship
at **`core`**. Every scaffold is a python project. `--language` chooses whether a
*second* toolchain joins the first — it has never been able to remove one.

So a `--language node` scaffold documented `npm install` and nothing else, and
line two of its own Quick Start — `./<cli> check pre-push` — invoked a python CLI
whose interpreter and dependencies the block above it never installed. Twenty-three
python test files, five `pip install -r scripts/requirements.txt` steps in its own
CI, and a setup section that mentioned none of it.

**It was invisible on the machine that wrote it.** `CLI_WRAPPER` looks for
`.venv/bin/python` and falls through to whatever `python3` it finds, and this
developer box has `click` installed system-wide, so the command ran. Reproduced
with a click-free interpreter it stops dead:

    ❌ The Probe CLI requires 'click'.
       Install with: pip install -r scripts/requirements.txt

— naming the step the README had not given. That is the `--pythonpath` lesson
from the pyright gate, on a different axis: same tree, same command, opposite
answers, decided by a package nobody installed on purpose. It is also the third
time the setup path has shipped broken here, after PEP 668 and the PATH lookups,
and the first time on the language axis rather than the platform one.

The fix is that the python steps are unconditional and `--language` only ever
appends. What generalises is narrower than "test every flag combination":
**a flag whose options look parallel is worth checking against what the tiers
actually ship**, because the asymmetry lives in the overlay layout and the flag's
own signature cannot show it.

### Two questions about one artifact, and only one of them is the tree's

stash.flow prototyped the setup-block drift check in their tree and it ships here
largely as they wrote it: enrolment by fenced `bash` block, a `cd` on the first
line excluding a sub-component with its own toolchain, an authority check for the
requirements filename, and a ratchet for the shared prefix whose floor is
*measured, not chosen*. Their argument for the split is the part worth keeping —
**a requirements filename has an authority and a shared prefix does not.** Three
documents disagreeing about a command is a vote with no tiebreaker, so the prefix
can only be defended as "the agreement does not quietly get smaller"; a document
disagreeing with `ci.yml` is a defect with a direction.

Two changes were needed to make it a template gate, and both are the same class
this repository keeps finding — a claim measured on one point of an axis, written
into a file that ships at every point.

**Enrolment named one toolchain.** `pip install -r <file>` is what a python
reader writes, and it enrolled **zero blocks** in a node tree, where `scanned(...,
least=2)` correctly turns a silent nothing into a red. The predicate names both.

**The floor is language-dependent** — 2 shared lines for `python`, 3 once node
joins. A `min_shared_prefix` baked into the template would be right for one
`--language` and red on arrival for the others, which is invariant 6 with the
axis changed from time to space. It is rendered instead, from
`len(setup_commands(language))`, which is the same source the blocks themselves
come from.

That last one forces a second gate, and the split is the interesting part.
`bin/skeletor-verify` sets `gated_language = "python"`: a node tree is scaffolded
but its own test suite is never run. So the shipped test can never check itself
on the axis its inputs vary along. The generator's gate asks the question no tree
can ask about itself — *is the pin this tree was handed the right one, and does
every language install its own toolchain* — and runs for every configuration; the
tree's test asks whether the blocks have drifted since, which the generator
cannot ask because there, one substitution fills all three.

**Same artifact, two questions, two homes.** The rule is not "downstream" or
"upstream" but *which side can be wrong about this*.

Established by planting four bugs, each asserting its target existed first: a
drifted venv line (prefix 2 → 0), an invented `requirements-dev.txt`, a floor
rendered one below the truth, and the node bug itself. The fourth is the one that
argues for two checks rather than one — with `npm install` alone in all three
documents the prefix stayed at its rendered floor and the doc-to-doc half had
nothing to say, because three copies of one wrong string are maximally
consistent. Only the authority check fired. stash.flow predicted that case
before either of us ran it.

### Two ways a plant can lie, both hit in one afternoon

The rule here was already *a plant that did not land is indistinguishable from a
gate that works*. Both failures below are that rule's other face — the plant
landed, and something else made the result meaningless.

**The revert overshot.** Undoing the first plant with `git checkout
bin/skeletor-new` reverted the plant *and* the two uncommitted real edits in the
same file, silently. The next control run came back red for a reason that had
nothing to do with what was being tested, and the error — `unknown placeholder
{{SETUP_SHARED_PREFIX}}` — pointed at the template rather than at the revert. A
plant is an edit to a working tree, so undo it with the inverse edit, asserted
the same way the plant is. `git checkout <file>` is not an undo of a plant; it is
an undo of the file.

**The control passed having run nothing.** Checking the shipped test against the
plants with the system interpreter printed `4 passed` for the control and green
for all three plants, because that interpreter has no `pytest` — the last line of
output was `No module named pytest` and the harness was grepping for the word
`failed`. A test run that could not run is not a pass, which is `filesAnalyzed`
and the ratchets' *"I could not measure" is not "the budget is respected"*
arriving in a five-line scratch harness. The habit that catches it is cheap:
**state the expected result before running, and let the harness say which it
got** — a control expected green and a plant expected red cannot both be
satisfied by an empty run.


### The manifest advanced past a file it had just refused to touch

A run that applied some files and conflicted on others copied the head render's
manifest **verbatim**, which recorded the new render's hash for a file the new
render had never reached. The next run then took that change as already in the
base, the base→ours diff no longer contained it, and it was never offered again.
Silent, permanent, and green in every gate.

stash.flow hit it on a real upgrade — a conflict on `AGENTS.md`, four other files
applied, `.skeletor.json` → v0.6.0 — and ported the patch by hand because they
had already read the sidecar, which is luck rather than process: `tmp/` is
gitignored and the next real run clears it before writing. Reproduced here at
once, and the second run's answer is the whole report:

    ✅ already current — nothing to carry over

about a change that had never been made.

The reason it is not a small bug is the manifest's shape. `cross_check` requires
its hashes to be **exactly** the render at `skeletor_ref` — that bijection is
what lets the offline fallback classify at all — so the manifest is a
single-version snapshot, and a partially-applied upgrade leaves a tree that is
not at a single version. There is no way to record "these files moved and that
one did not" in it. Selectively keeping the old hash for the conflicted file
fails the bijection and every later run refuses.

So the fix is to hold the whole thing back: **a run that leaves anything pending
does not advance the base.** That is sound in the direction that matters. The
applied files then differ from their recorded hash, so the next run reads them as
edited and merges rather than replaces — and that merge is clean, because theirs
and ours already share exactly the hunks that were applied. A superfluous merge
is the cheap error; a lost template change is the expensive one.

**The fix creates the state that needs `--ported`**, which is why they ship
together rather than in sequence. A tree whose divergence is permanent — an
adopter's `AGENTS.md` they have no intention of surrendering — would otherwise
hold its base at the last fully-applied release forever, re-offering the same
conflict at every tag and growing the merge span with each one. `--ported` is the
user asserting the tree is now at this version: they took our change, or they
took their own and mean it.

It has to be a flag rather than an inference, and the reason is worth stating
because it looked at first like a reason not to build it at all. Nothing can
verify a hand-port: a three-way merge cannot distinguish "already applied" from
"never applied", since re-merging an applied hunk conflicts exactly like an
unapplied one. So the tool would be guessing, and the wrong guess is precisely
the silent loss the default now prevents. Named, with every file it trusts listed
and the consequence spelled out, it is a decision. Inferred, it is the same bug
wearing a flag.

The earlier reading here was that a global `--ported` was *unsound* because one
un-ported file would lose its change. That was right about the mechanism and
wrong about the baseline: the default path was already doing exactly that, with
no flag and no assertion. stash.flow's framing is the correct one — **the
soundness condition was not a new requirement the flag introduced, it was an
existing invariant the default already violated**, and the flag is the first
place it can be said out loud.

Two smaller things came with it. The conflict report now says the sidecars are
the only copy and that the next real run clears them, which converts a silent
expiry into a decision — stash.flow's tell was that a *stale* sidecar already
gets a warning while one about to be overwritten unapplied got none, and the two
look identical on disk. And that paragraph is emitted in two versions, because
only one is true on any run: under `--ported` the base has already moved past
them, so re-running will not regenerate them. Printing both would have been this
document's own invariant 7, in the commit that fixes an instance of it.

### Every gate ran against a tree where the branch could not be reached

`sidecar_gate` already said the conflict and collision branches are unreachable
from a fresh scaffold, and manufactured them with `--no-base`. That flag cannot
manufacture *this* one: under it a fresh scaffold matches every recorded hash, so
nothing applies, and the manifest only moves when something applied **and**
something did not. The combination needs a real version gap and a real
conflicting edit, and that is why the bug lived through every release that had
these gates.

`pending_ref_gate` builds it. Three things about how, each of which was a wrong
first draft:

**The plant is derived, not quoted.** The same configuration is scaffolded at the
tag and at HEAD, and the first line where a file's two renders differ is the line
the template is about to change; the tree gets a third value there. A quotation
from one release would go stale at the next.

**Both trees take the same final path component.** `--slug`, `--cli` and
`--env-prefix` all default from the target directory name, so scaffolding into
`pending-head/` and `pending-scaffold-0/` made the first differing line
`name: pending-head-documenter` — a difference caused by this gate's own workdir
layout rather than by the template. It planted there for all 38 tags and
conflicted against an artefact. *The example you reach for first cannot
discriminate*, arriving in a derivation rather than a fixture.

**The plant is committed before the upgrade runs.** Otherwise the tree is dirty
and `refuse_a_dirty_tree` declines, so `conflicted=False, applied=False` on every
candidate — a gate red for a reason unrelated to its subject. Both of these were
found by reading the attempt log the gate prints, which is the only reason the
first green would not have been believed: it names the file and line it planted
in, so a plant in the wrong place is visible rather than merely unlucky.

Planted the original bug back and required red. Both assertions fire — the ref
advances, and the second run says "already current".

### The condition that narrows on the wrong end

`sidecar_gate` reaches the conflict and collision branches, `pending_ref_gate`
reaches the manifest-advance branch, and both are branches with *something to
report*. The third way out of an upgrade is the one with nothing to report, and
it `return`s before the footer — so the stale-sidecar warning, the sentence that
exists because a fresh patch and a four-day-old one look identical on disk, was
unreachable from **dry run, already current, sidecars present**. That is the
case where every file in that directory is stale by definition rather than
merely possibly, since there is no plan above for any of them to belong to, and
it prints under the most reassuring line this tool has.

stash.flow reported it and named the class: **the warning is conditioned on
there being a plan to contrast against, and absence-of-plan is not
absence-of-hazard.**

The first generalisation written here was that this is the sibling of the rule
this repository already holds for negative assertions — there an empty
enumeration makes a check vacuous, here an empty plan makes a warning maximally
warranted and turns it off — and *therefore* a guard predicated on a quantity
being non-empty is worth checking against the empty case. stash.flow's
correction is the load-bearing half, and it is that the two point in **opposite**
directions from the same observation, which leaves "watch the empty case"
underdetermined: it says to look and not what you will find. What decides which
one you are in:

> **Ask whether the empty thing is what you *looked at* or what you *found*.**
>
> Empty **scope** — the enumeration, the file list, the scan — means nothing was
> examined, so every verdict over it is vacuous. That is `scanned()`, and it is
> the `--junitxml` ratchet: *"I could not measure" is never "the budget is
> respected."*
>
> Empty **finding** — the plan, the diff, the result — is a real answer, and
> frequently the most informative one available, because it can be the fact that
> makes some other hazard total. The plan being empty is not an absence of
> information; it is the reason every file in `tmp/upgrade/` is *guaranteed*
> stale rather than possibly stale.

Both are "a quantity was zero". One is a measurement that did not happen and one
is a measurement that came back, and the failure here was reading the second as
the first. That also explains why it outlived every gate: all three of the
upgrade gates reach branches with something to report, so all three test the
*scope* end. Nothing had ever asserted on a branch whose finding was
legitimately empty — and that is the common branch, precisely because most runs
have nothing to do.

That is not a lapse, and stash.flow put the mechanism harder than "the natural
way to write a gate": **you reach a branch by manufacturing an input that makes
it fire, so every gate you write tests, by construction, the end where something
is present.** The empty-finding branch cannot be reached that way — there is
nothing to manufacture. You have to arrange for *nothing to happen* and then
assert about it, which does not occur to anybody writing a gate for a bug they
just watched. Expect it of any gate suite here until somebody names it, which is
what this paragraph is for.

The prose rule that got corrected has the same shape as a defect this repository
already knows in code. **A rule that cannot be wrong is a rule that cannot
help** — and *"a structural gate you had to allowlist five things to ship is
describing the wrong shape"* is that property in the other medium, a predicate
that accommodates every case having stopped discriminating. The difference is
that the code version leaves a receipt: the allowlist accumulates and you can
count it. Prose accumulates nothing, so the only tell is that the rule keeps
getting confirmed and never bites — which reads as evidence for it.

The same line had a second defect, and it cost one string: **"already current"
named no version.** The run compares the tree against a render of skeletor's
HEAD, so that is the claim — but the manifest is re-copied only by a run that
*applies* something, so an already-current tree keeps recording the ref it was
scaffolded at forever. A reader holding that line next to `.skeletor.json` had
no way to tell "current with HEAD" from "current with the ref recorded there",
and the two genuinely differ. Both now print, and `head_ref` joins `base_ref` in
the `--json` envelope, because a machine consumer reading an empty diff off the
base ref alone has exactly the same ambiguity.

The gate for it is a third scaffold in `sidecar_gate` — clean, sidecars planted,
one dry run — asserting the named ref equals the manifest's and that **every**
planted sidecar appears by path. Every one, not one of them: the listing
truncates at ten, so "it mentioned something" would pass a report that dropped
the rest. Required red against the pre-fix script first, where the line carries
no version and the sidecars go unmentioned entirely.

### A verdict that changes with the neighbours

`check_doc_links.py` crashed on a link that left the repository.
`target.relative_to(PROJECT_ROOT)` raises `ValueError` for a path outside the
root, so a single `[x](../sibling-repo/GUIDE.md#anchor)` took the whole check
down in a traceback that named pathlib and not the link. Reported by
skyrow-workspace, a repo built entirely on sibling checkouts, where it was
latent: their one out-of-repo link has no fragment, and the crash is in the
dead-anchor branch.

The interesting part is that fixing the crash is the wrong fix. The question
underneath is whether such a link should be checked at all, and it should not:
**whether `../sibling-repo/GUIDE.md` resolves is a fact about what is checked
out beside this tree, not about this tree.** True on the machine the docs were
written on, false on a runner that cloned one repository — and this checker is a
*ratchet*, so a verdict that changes with the neighbours breaks the build on the
CI runner while every local run is green. Rendering the path more carefully
would have kept a check whose answer nobody can rely on and made it quiet.

So a link that walks out is out of scope by construction, which makes the
`relative_to` unreachable rather than guarded. It is **counted and named on
every run** — `skip()`, not silence — because an unchecked link inside a clean
report is precisely the failure `markdown_files()` was widened to prevent. That
is empty-scope-versus-empty-finding one more time: the links are a real finding
about what this checker cannot answer, and dropping them would have made the
scope smaller while the report looked identical.

Three things it cost that the bug report could not have named:

- **There were two sites, not one.** `repoint_fragments()` formats the same
  path, and `--fix` runs it *before* `scan()` — so every run that reached the
  reported crash had already survived the other one, which needs an anchor with
  exactly one obvious successor to get far enough to format anything. The
  convenient reproduction reaches neither the second site nor, in `--fix`, any
  file: the exception escapes the loop before the write pass, so one out-of-repo
  link silently turns the repair tool into a no-op for the entire tree.
- **The boundary is a property of the href, not of the filesystem.** The first
  fix asked `Path.resolve()`, which follows symlinks — so a document that is a
  symlink into another checkout, one file with one home in two repositories,
  became out-of-repo and kept raising. `os.path.normpath` collapses `..`
  textually and answers the question actually being asked: *where does this link
  point*, not *which file is this*. `exists()` and `read_text()` follow symlinks
  themselves, so resolving bought nothing it was not also breaking.
- **The fixture that shows it cannot be the fixture already there.** The
  existing one puts the repository at `tmp_path`, which leaves nowhere to *be*
  outside it — the out-of-repo case is unreachable from it, not merely untested.
  The new one nests, and asserts the sibling file really resolves before
  planting, since a target that does not exist tests "does not exist" instead.

The other half of that report is not a bug and is worth naming as such:
`SCAN_ROOTS` is `docs`, `.claude`, `.github` plus every root `*.md`, so a repo
whose prose lives in `strategy/` adds a line. That is adoption cost, correctly
placed — the roots are bounded on purpose, and a discovered-everywhere rule
would walk `template/`, `node_modules` and every vendored tree in repos that
have one.

### The generic name, claimed by the specific thing

`cli/` is a literal directory in the template — no placeholder, no flag. It is
in `python -m cli` in the wrapper, in `from cli.helpers import ...` in every
command module, in `CLI_DIR`, in the tests and in the docs: 54 occurrences
across 29 files. `--cli` renames the *wrapper script* and nothing else.

Reported as skeletor owning a project's CLI, which is worth separating into the
part that is true and the part that is not. Nothing under `template/*/cli/`
mentions skeletor or calls back to it — `check`, `docs`, `test`, `commit`,
`worktree`, `report` are the project's own gates over the project's own tree.
What skeletor keeps is the right to *update* those files on upgrade, which is a
different claim and the one that actually constrains a consumer.

The clash is narrower than the report and completely real inside its range:
**when the product is itself a command, the dev CLI and the product CLI want the
same name and the same package.** Three shapes, and the tell is a question
nobody was being asked —

- the product is not a command (a service, a site): the two names are one word,
  and the slug-derived default is right;
- the product is a command shipped from its own package: give the wrapper a
  shorter name. proto.pilot scaffolded `./pp` beside `proto` from `protopilot/`;
  mind.head scaffolded `./mh` beside `mind-head` from `mind_head/`. Two
  consumers reached the same arrangement independently and neither wrote it
  down, which is the definition of an undocumented convention;
- the product *is* `cli/`: sky.boss, which has no `.skeletor.json` at all. It
  declined adoption and used `bin/skeletor-components`, which is the tool for
  exactly that case.

So the fix is the routing, said once in `AGENTS.md` where the five questions are
asked, and not a rename. Renaming the package to `dev/` would be mechanical here
and unaffordable downstream: **`bin/skeletor-upgrade` cannot rename a
directory.** It renders the new tree, so `dev/*.py` arrive as new files and
`cli/*.py` are *reported* as no longer shipped — never deleted, deliberately —
leaving every adopted tree with two packages and a wrapper pointing at one of
them. A migration wearing an upgrade's clothes.

A `--cli-package` placeholder would be affordable — the same mechanism as
`CLI_WRAPPER`, plus one verify configuration with a non-default value, since a
flag never observed to disagree with another flag is undistinguished rather than
confirmed. It is not built, because the one consumer it would serve already has
an answer it chose on measurement, and a second door to a solved problem is how
two mechanisms start disagreeing.

### Two guards, each right, and a documented flow neither could reach

`bin/skeletor-upgrade` told you to port the conflicts from `tmp/upgrade/` and
re-run. Neither half of that sentence worked.

**A plain re-run never advances the base.** A hand-ported file no longer matches
its recorded hash, so it comes back as an edit and three-way merges — and a
merge cannot tell an applied hunk from an unapplied one, so it conflicts again,
`pending` stays non-empty, and the ref stays where it is forever. The flag that
does advance it is `--ported`, and the instruction did not name it. The code
comment three lines below the message says exactly why a merge cannot tell, so
this was two correct statements that never met.

**And `--ported` refused a dirty tree, which the flow guarantees.** The run that
produced the conflicts had already written every file it could apply, so the
tree is dirty from the tool's own output *before* the first hand-edit. That left
two exits and both are bad, which is how proto.pilot found it: commit with the
manifest knowingly at the old ref — the record corruption every other guard here
exists to prevent, reached for *because* you are being careful — or pass
`--allow-dirty`, whose help describes merging into in-progress edits of your
own. There were none. The dirty tree *is* the tool's output, so the flag that
works reads wrong, and they backed three files up by hand before trusting it.

Neither guard is wrong and what they jointly imply is: the class this document
already records as the defect that lives in what two files jointly imply,
arriving this time between a guard and an instruction.

The fix names the missing fact rather than relaxing anything. **A conflicted file
is never written by this tool**, so `--ported` cannot overwrite a hand-port — it
moves the record, not the bytes. That sentence is now in the flag's help, in the
warning that replaces the refusal, and is why a warning is the right shape: a
refusal is only a refusal if its escape hatch fits the case, and otherwise it is
a riddle.

The gate rides on `pending_ref_gate`, which already manufactures the only state
in which `--ported` is warranted — a run that applied some files and conflicted
on one — and leaves it uncommitted, which is what makes it the right host.
Committing between the runs is precisely what a careful reader does to get past
the refusal, so a gate that committed would arrange the bug away. Both
assertions were established by planting: the refusal restored, and the manifest
copy removed so `--ported` proceeds without advancing anything.

`--dry-run` got the same treatment from the other direction, on proto.pilot's
observation rather than their request. It is never refused a dirty base, and that
is correct — nothing is written, so the unreproducible-render hazard cannot
land, and it is what lets `bin/skeletor-verify` run `--from-dir .` against this
checkout mid-edit. But a dry run is the thing somebody *reads to decide*, so a
plan computed from a base that exists in no commit is exactly where it matters,
and it arrived looking like any other plan: this checkout was mid-pass, their dry
run planned two files, and a real run from a clean tag correctly left both alone.
It warns now, once per checkout — twice was the first draft, because a dry run
reaches the check for the base and again for the head render, and with
`--from-dir .` those are one directory. The refusal never showed that, because it
exits on the first call.

### One finding printed, four withheld

`test_every_cited_path_exists` asserted inside its loop, so it reported the
alphabetically first dangling citation and said nothing about the rest. That is
this repository's count-versus-set rule with *failures* substituted for tests: a
single reported failure is a negative assertion over the remainder, and it looks
identical to there being no remainder.

It matters most at arrival, which is the only moment an adopting tree meets every
finding at once. proto.pilot landed red with five, read one, and concluded that an
exclusion they had written was unnecessary — it was necessary by three, all
behind the first `assert`, alphabetically. They caught it only by running the
finder by hand afterwards instead of trusting the line.

The template already shipped the principle: `docs/DEVELOPMENT.md` says *"Every
gate runs even after one fails. One fix per round trip is the thing this exists
to avoid."* A new gate broke a rule the tree states in prose, which is the
argument for Rule 2 in miniature — a convention you must remember to apply is a
registry with no enforcement.

### A ratchet that varies by time, and a rise with two readings

`setup_block_budget.json` is written by the scaffolder because the shared-prefix
depth varies by `--language`. Its comment anticipated that axis and not the other
one: arriving through `bin/skeletor-upgrade` into a tree scaffolded long ago, it
carries the floor for a *fresh* scaffold, and a tree that has since converged
further is red on arrival. Red **upward**, with "raise it to 4" in the message —
which is the ratchet asking you to lock in a gain, not a defect, and one
documented line is the whole remedy. It is now that line, in the file the reader
will have open.

`bin/skeletor-upgrade` re-measuring and writing the floor was considered and
declined. A tool that rewrites a ratchet's floor to whatever it currently
measures has stopped being a ratchet, and the one moment it would need to is
adoption — where a human deciding is the entire point, and where this repository
already says to baseline at what the repo has.

The same file gave up a better bug. Its docstring opened *"`README.md`,
`docs/DEVELOPMENT.md` and `AGENTS.md` each carry the install steps"* as fact,
while enrolment is by content and `least=2` tolerates two — so a tree whose third
document legitimately stopped being an install block ran a two-way comparison
under a three-way claim, silently. Invariant 7 again, on the axis that has now
produced three instances: a count measured in one configuration, written into a
file every configuration carries.

But it was not invisible, and that is the useful half. Fewer blocks almost always
agree *further*, so a departure surfaces as a rise in the depth ratchet — which
proto.pilot hit at 4 against a floor of 2. It surfaces unreadably if the message
omits the list, and it did: the shrunk branch named the enrolled blocks and the
grown branch did not, so the branch an upgrade actually produces was the one with
no way to tell "we got tighter" from "one of us left". Both branches name them
now. No new ratchet on the block count, deliberately — a floor there would
manufacture a red on precisely the trees whose divergence is correct, which is
the previous finding arriving from the other side.

### The registry that went stale exactly once, and how that was established

`write_manifest` recorded fourteen flags from a hand-written list.
`--versioning` arrived later, changed what ships, and never reached it — so
every `--versioning tag` tree recorded arguments that re-render as a
release-please tree. `cross_check` then refused on four wrong hashes and three
produced-but-unrecorded files, which means those trees were **permanently
unupgradable**, `--repair-manifest` included, since it re-derives from the same
wrong base. Release-please trees were unaffected only because the default
happened to match. This is Rule 2's own failure mode landing in the file that
argues Rule 2 three functions away, in `produced_files()`.

node-zero found it and proved it **differentially** rather than by inference:
the same committed ref, rendered once with the recorded args and once with
`--versioning tag` added — 4 mismatched and 3 unrecorded against 0 and 0, with
all 102 hashes reproducing bit-for-bit. That distinction turned out to predict
correctness better than agreement did on this round: three sources, reasoning
from the mechanism, had separately concluded that a `-dirty` ref made node-zero's
base unresolvable, and the one source that re-rendered found the opposite. The
code they all read past says so, and records that proto.pilot had corrected the
same point here once before.

**"The list is wrong exactly once" is a measurement, not an inference**, and it
was made because the one-instance phrasing invites the question a hand-written
list has no reason to answer. Recomputed over the full set: 17 flags declared,
14 recorded, 3 declared-but-not-recorded — `--force` and `--no-git`, each read
once and neither reaching a render, and `--versioning`. So it is the only
render-affecting flag missing, over the whole set rather than the lucky hit.

The fix is to stop keeping the list. `manifest_args()` derives the record from
`build_parser()`, so a flag is recorded by existing, and two small maps remain
for the two things a parser cannot say: which flags do not reach a render, and
which four record their *derived* value because they default from the target
directory name and an upgrade re-renders into a different one.

`manifest_args_gate` guards what is left, in both directions — a declared flag
that is neither recorded nor exempt is the original bug, and an exempt name that
is no longer a flag is an exemption nobody chose, waiting to pre-exempt whatever
claims that name next.

**Its scan proves itself differentially rather than against a floor**, and that
came out of the round too. proto.pilot's first pass at this counted the manifest
list by reading to the first `]` — which lands after `values["PROJECT_NAME"]` —
got 1 of 14, and reported 16 missing flags. Their non-vacuity guard passed,
because one is not zero. A `least=1` floor cannot tell a working scan from a
93%-blind one; on that scan it actively certified it. So the flags are read
twice here, out of `parser._actions` and out of the usage line the parser
prints, and the two sets must be equal. Two readings disagreeing is a fact about
the reading. One reading clearing a bar is a fact about the bar.

All four branches were planted and required red, and the plant that mattered is
the one that did not work first time: adding a new flag to the parser passes
green, because the derivation records it by existing. Reaching the "declared but
not recorded" branch takes planting the *derivation* skipping a flag — which is
the old hand-written list, re-created. A plant that reproduces the fixed
behaviour is not a plant.

(A restore that did not land looked identical to a gate still failing, for the
same reason and one layer down: `SourceFileLoader` caches bytecode by mtime and
size, `[a-z]` and `[\w-]` are the same length, and both writes fell in one
second. The cache is cleared between plants now.)

### Two `cli/` packages and one terminal in the wrong directory

`python -m` prepends the current directory to `sys.path` **ahead of**
PYTHONPATH, and every scaffold contains a `cli/` package. So a scaffold's
wrapper run from inside another skeletor tree imported *that* tree's CLI: it
came up under the other project's name, with the other project's commands,
operating on the directory it was standing in, exit 0 and not a word. Measured
rather than argued — two probe scaffolds, `./shadowb` from `shadowa/` printing
`Usage: shadowa`.

sky.boss found it and had been bitten by the same mechanism before, which is why
this is gated rather than fixed and forgotten: generating systemd units from
inside an older checkout wrote every unit with the wrong `WorkingDirectory`,
successfully and silently. Anything that writes a path is exposed, and the
triggering condition is a workspace of sibling checkouts, which is ordinary
rather than a corner.

`export PYTHONSAFEPATH=1` in the wrapper, one line, no render change, and it
fixes every tree that already exists on its next upgrade. `shadow_gate` asserts
both directions: a wrapper answering correctly from its own root was always
green and proves nothing, and a gate running only the cross-tree invocation
would be satisfied by a wrapper too broken to start.

### The warning that arrives after the write

`--force` is step 1 of adoption — `AGENTS.md` calls scaffolding into a
repository somebody already works in *the usual case* — and it overwrites
without asking. The losses are silent by construction: a file that is gone
raises nothing. The scaffolder named them, which was the right fix, but it
named them **after** the write, which makes the list a post-mortem.

The measurement that settles it: **`CLAUDE.md` collided in four adoptions out of
four.** Every adopter overwrote the file holding whatever agent instructions
their project already had, on the documented first command, and found out from
a report printed underneath the damage. That is not a risk profile to be
weighed, it is what the command does.

`--dry-run` renders into a temporary directory and prints what a real run would
write and which of your files it would replace, creating nothing. Two design
choices are load-bearing:

* It **renders**, through `copy_overlays` and `post_copy_steps`, the same
  functions the real run uses. A dry run that reproduced the loop would be a
  second reading of the same intent, and the two would answer differently the
  first time an overlay grew a rule.
* It is **not refused** for a populated target without `--force`. Being told to
  pass `--force` in order to discover what `--force` would destroy is the shape
  the flag exists to remove.

The gate asserts the tree is byte-identical afterwards, that an absent target is
not created, and — the assertion with teeth — that the prediction **equals what
the real run then reports**, file for file. "Writes nothing" is easy to satisfy
uselessly; a dry run printing a plausible number passes it.

That comparison earned itself before it ever ran in anger. The first version
predicted from the pristine render while the real run's warning intersected
`written`, the copy phase alone — so `regen.py` overwrote a user's own
`docs/todo_index.json` and the warning whose entire job is completeness did not
name it. **The manifest bug, in the warning about the manifest bug**, found by
building the thing that predicts it. The two are one set now, which is what
makes the prediction worth anything.

### The default that every tree able to see it was structurally unable to see

`scripts/paths.py` shipped

```python
STATE_ROOT_ENV = "SL_AGENT_LOGS"
STATE_ROOT_DEFAULT = Path.home() / "skyrow.labs" / "sl-agent-logs"
```

in `template/core/`, so **every tier** — a scaffold made by anybody, anywhere,
put its transcripts and ledgers under a directory named after somebody else's
company, and read an environment variable whose prefix is that company's
initials. Neither is a preference that happened to be wrong; both are one
workspace's local convention published as a generator's default.

What makes it worth a section is why nobody caught it. mind.head measured their
own tree and reported the thing they could not have found by running it: the
default **resolves correctly there**, because that tree lives under
`~/skyrow.labs` and the path exists. Their four gates pass. So do everyone
else's — stash.flow, node-zero, proto.pilot and sky.boss are all siblings under
the same root.

> **The five trees best placed to report this are the five that cannot.**

That is the workspace's seam rule arriving from the other side. A suite cannot
find a disagreement about an artifact when its writer and its reader share the
mistake, and here the template learned the convention *from* the neighbourhood
it was then tested in. Four green adoption reports are evidence about a great
many things and no evidence at all about this line. It is the emptiest kind of
green: not unexamined, but examined by parties who agree by construction.

The replacement is a shared root with `STATE_SLUG` below it, unchanged in shape:
`~/.local/state/agent-logs`, where a state file that is neither cache nor config
belongs, with a distinctive tail because `test_state_paths.py` has to recognise
a second definition of it by name. The environment variable takes the project's
own prefix and stays the **first** thing checked — mind.head's condition, and
the right one: an override is how an adopter whose environment disagrees with
the default fixes it without diverging the file, and a file nobody has diverged
is where a template change arrives as a silent clean apply.

Two second homes came out with it. The test's `ROOT_TOKENS` was a literal
`r"sl-agent-logs|SL_AGENT_LOGS"` — the second definition this test exists to
forbid, wearing the costume of the test that forbids it, and failing in the
reassuring direction: rename the root and the pattern matches nothing, so the
check goes green over a tree full of stale copies. It is read out of the
resolver now. And `AGENTS.md`'s Rule 14 stated the path in prose, which
`test_state_paths.py` cannot see because it scans `cli/` and `scripts/` for
Python. The rule forbidding a second definition of the path contained one; it
names `state_dir()` and tells the reader to ask it.

### A report and the deed it reports, separated by a condition

`--ported` is the user asserting a pending file is resolved, so the base may
advance past it. The advance sat inside `if not args.dry_run and (added or
updated or merged)`; the sentence announcing it — *"--ported already advanced
the base past them, so re-running will NOT regenerate these"* — sat eighty-nine
lines further on, keyed on `args.ported` alone. A conflict is in none of those
three groups. So an upgrade where **nothing applied and one file conflicted**
printed the claim over a manifest that had not moved.

Every consequence of that is bad in the same direction. The port is unrecorded,
so the identical conflict returns on every future run, permanently. And the
false sentence *disables the recovery*: `tmp/upgrade/` is gitignored and cleared
by the next real run, so a reader told the sidecars are the last copy will not
do the one thing — re-run — that regenerates them.

**The discriminating variable is that nothing applied, not that everything
pending is a conflict**, and the two are easy to confuse because they coincide
in the small cases. proto.pilot forced a real conflict on a real tree and the
base advanced correctly, because two unrelated files applied alongside it; their
run reads as a refutation until you notice which half of the guard it turned.
node-zero ran the controlled version — add one cleanly-applying file to the same
batch and the failure disappears.

Nobody in the fleet had met it, and the reason is the same coincidence: while a
template is weeks old and changing daily, every upgrade carries clean applies
that hold the guard true. **A conflict-only upgrade is the ordinary shape of a
mature one, so this defect gets more likely as the tool settles.**

`pending_ref_gate` could not see it either, and that is the sharper lesson. It
`continue`s to the next tag unless `conflicted and applied` — it selects for
exactly the safe side of the boundary the bug lives on. **A gate that requires
two things to be true cannot find a bug that fires when only one of them is.**

mind.head named the class, having found the same shape in a gate that printed ❌
and exited 0 — a discarded return code separating the report from the result:

> **A report and the deed it reports must not be separated by a condition.**

The failure runs in one direction, because the reporting path is the cheap one
to reach and the acting path is the guarded one, so the message survives when
the deed does not and the tool claims more than happened. Two instances shipped
here inside a fortnight and both failed toward claiming more.

The remedy is not a second copy of the condition, which leaves the shape intact
and two places to keep in step. **The acting path produces the message**: the
write sets `advanced`, and every sentence claiming the base moved reads it. The
advance knows whether it advanced; nothing outside it does. That is this
release's `--xml` fix generalised — a shared assumption makes two things equal,
a returned fact makes them connected, and connected survives one side drifting.

The fix carried a second defect out with it. The instruction naming `--ported`
lived on the branch that holds the base back, which was inside the same guard —
so a user meeting a real conflict was told to port by hand and **never told the
flag that records the port**. They port, re-run, get the identical conflict
(re-merging an applied hunk conflicts exactly like an unapplied one), and
conclude the tool is stuck.

Method, and it is the round's most transferable result: gap 5 stayed open for
four fleet upgrades of *upgrade and report what happened*, and closed in about
fifteen minutes once node-zero **constructed** the input — a scratch commit
against a clone — rather than waiting for a template release to produce the
shape. **For a behaviour that only fires on a rare input, waiting for the input
is not a test strategy.** That is the plant-and-require-red rule this repository
already applies to its own gates, applied to how the defect is reached.

### An extension point implemented as an edit is not an extension point

`v0.5.7` added `NARRATIVE` to `scripts/paths.py` so an adopter could declare a
documentation stage without diverging a shipped test. Its comment said so:
*extending this tuple is a one-line change to a file you own*. True about
permission, and wrong about the thing that matters.

stash.flow merge-tested it, and this repository reproduced the test in its own
source with `git merge-file` against a pristine render. Same intent, same
upstream change, two spellings:

    NARRATIVE = (TODO_DIR, IMPL_DIR, DOCS_DIR / "reports", EXPLORE_DIR)   CONFLICT
    NARRATIVE += (EXPLORE_DIR,)                                           clean

> **The discriminator is not permission, it is line disjointness.**

`.gitignore` and `.github/DOCS_INDEX.md` merge clean forever not because they are
blessed but because the adopter's lines and the template's lines are *different
lines*. Being invited to edit a line changes nothing about what git does when
upstream edits it too — and an extension point is, by construction, the line
upstream is most likely to change.

Two sites were shaped this way and both now carry an append slot with the
measurement beside it. A third, isort's `known_first_party`, cannot be: TOML has
no append, and saying so at the site is better than pretending the shape is
uniform.

No gate. Two sites, a comment at each, which is mind.head's arm of this
repository's own rule — *derive it, or say where it rots* — and a gate for two
entries is the over-building that teaches people gates are noise. What earns a
gate is a set large enough to drift unnoticed.

### A default that never rendered the interesting case

`--base-branch` defaults to `develop` and `--release-branch` to `main`, so every
tree `bin/skeletor-verify` had ever generated carried two distinct names. The
bug lives entirely where they are equal — which is every repository while it is
one person, and node-zero's tree. Three workflows rendered `branches: [main,
main]`, and `AGENTS.md` rendered *never on `main` or `main`*, in the document
that establishes the rules, which is the file an agent opens first.

The pair is computed once in `substitutions()` now, because the sites cannot
dedupe it themselves: one is YAML and one is prose, and neither language can ask
whether two substitutions came out equal.

`branch_gate` asserts both configurations, and the second keeps the first
honest — a substitution that collapsed unconditionally satisfies "no duplicate"
while silently dropping the integration branch from every two-branch repo's CI
triggers. Same fix, failing the other way, with nothing red to say so. Each
direction was established by planting it.

The general form is the fixture rule this document already states, on the axis
of defaults rather than of examples: **a flag's default decides which
configuration your gates have been checking, and the interesting case is
usually not the default.**

### Two manifest bugs, opposite signs, one line

They arrived a day apart, from different repositories, with different symptoms,
and everybody involved — me included — treated them as two items.

**Under-record.** A second `--force` drops four files from the manifest.
`regen.py`'s outputs are shipped by no overlay, so they enter only by changing
across `post_copy_steps`; on the second run they already exist with identical
bytes, regen no-ops, and they leave silently. Measured 126 → 122 into a tree
skeletor itself had just made, `--agent none`, no adopter content anywhere. The
absolutes are config-dependent and the file set is not: it is always
`docs/TODO/README.md`, `docs/implementations/README.md`, `docs/todo_index.json`,
`docs/implementation_index.json`.

**Over-record.** `add_frontmatter.py` stamps lifecycle frontmatter onto an
adopter's own plans in `docs/TODO/`, which is its job. Their hashes move across
the same two snapshots, so documents no render can produce get recorded as
skeletor's. mind.head measured 124 recorded against a true 105, and every later
upgrade refused on a *wrong hash* — worse than the surplus-entry refusal
proto.pilot hit, because a surplus entry can be deleted by hand and a wrong one
cannot.

Both are `produced = produced_files(written, after_copy, final)`, and the
diagnosis that makes them one is sky.boss's:

> `produced_files()` asks "did this run write it", where `cross_check` asks
> "does the base render produce it", and an idempotent generator is exactly
> where those two questions diverge.

The manifest's question is `cross_check`'s. On a populated target the base
render is already standing there — `pristine_post_copy` runs the post-copy
steps against the render alone, precisely so the recorded *hashes* describe
something reproducible — and it was being consulted for the values while the
*membership* still came from a walk of the real tree. So `pristine` decides
membership too, and both signs go at once: it is neither too small on the first
count nor too large on the second, by construction rather than by correction.
For an empty target it is `{}` and cannot be consulted, and there the tree *is*
the render, so the old computation is exact.

`populated_tree_gate` already compared a `--force` manifest against an
empty-directory one and could see neither. Its populated tree is decoys, and its
`--force` is a *first* one — the fixture rule again, in the place this document
already warns about: the tree you reach for first has no skeletor history, and
the entire defect is about what the second run believes it did. `rescaffold_gate`
scaffolds twice into one tree with a plan written in between, and its plant
turns all three assertions red, the independent upgrade reading included.

Worth keeping about the process rather than the code: the first mechanism
offered for the under-record was the over-record's, reached by a longer road —
an adopter writing plans between two runs. It was plausible, it was endorsed by
more than one reader, and it was wrong; the run that falsified it took four
commands. mind.head stated the risk before either was touched — *if you fix the
plausible common cause and it is two causes, you will fix one and believe you
fixed two* — and the answer turned out to be the other way round, which no
amount of reading would have settled. Two bugs, one line, established by
reproducing both in a single tree.

### A guard asking a broader question than it needed refused every adopter

`bin/skeletor-upgrade` renders a tree's base from this checkout, so it refuses
to run against a dirty one — a base rendered from uncommitted edits is a base
nobody else can reproduce. Correct, and scoped to the wrong question. It asked
whether the *checkout* was clean; what it needs to know is whether the *render*
is reproducible, and those differ by everything outside `template/` and
`bin/skeletor-new`.

The cost was measured in one round: an untracked `notes.md` at this repository's
root — a draft tag annotation, twenty-eight lines, touching nothing — refused
all four adopters, and three of them worked around it by cloning at a tag —
precisely the fallback the guard exists to make unnecessary. A refusal that
people route around has stopped being a guard.

The count is three rather than four, and how it got there is its own small
lesson. "All four worked around it by cloning at a tag" was relayed to me,
repeated by me into a pushed commit message, and then came back from the same
session as corroboration. Sourced afterwards, one at a time: mind.head,
stash.flow, and node-zero — who were refused with `notes.md` named and followed
the tool's own printed remedy. proto.pilot is still unsourced. **A relayed
number does not merely travel — it can be written down by the party best placed
to be believed, and return to its originator looking like confirmation.** What
was safe to assert before the sourcing is a property of the guard rather than of
anybody's remedy: it refused every one of them.

The near miss is worth keeping too. The sentence that would have sourced
node-zero *did* exist and said the opposite — they had described the clone as a
preference — but it came from a later round, after this guard was fixed, when
they were rendering pristine trees rather than upgrading. **A quotation carries
the round it was said in, and a session that has done two things has two
answers.**

`reaches_a_render()` is a prefix test over the render inputs, not a list of
files to ignore, and it reads both sides of git's `old -> new` rename form. The
gate holds both directions, because narrowing a guard is exactly where you stop
noticing it narrowed too far: an untracked file under `template/` must still
refuse, and one at the root must not. node-zero reported it and supplied the
predicate.

### A gate that reported its own failure as success

`<cli> test coverage` ran pytest with `--cov --cov-report=term-missing` and no
`xml:` report, then handed `check_coverage_budget.py` a path nothing had
written. The ratchet said `❌ no coverage report at tmp/coverage.xml` — and the
command exited 0, because the checker's return code was discarded. Both halves
shipped in every tier.

That pairing is worse than a check that never runs. A silent gate is at least
consistent; this one printed the red where a human could see it and told every
caller above it that the budget held. It is the `--junitxml` hole in `ci.yml`
one layer down, and it survived for the same reason: `bin/skeletor-verify` runs
a tree's suites *directly*, so the flags a wrapper passes were never executed by
anything. The seam is not upstream-versus-downstream but *which side can be
wrong about this* — and a wrapper's arguments are a question only the wrapper's
own invocation can ask.

`coverage_gate` runs the tree's own command, then raises the baseline to 99.9%
and requires a non-zero exit. Both halves are load-bearing, and each was
established by planting it: without the first the gate passes on a tree that
measures nothing, and without the second it passes on the bug that shipped.

### A recipe and its guard, written by one hand

The upgrade footer tells a reader not to verify by counting tests, and hands
them a recipe that diffs the collected ids instead. Its third line ran an
unscoped `pytest --collect-only` from the tree at the moment `tmp/pre-upgrade`
existed — created one line above, removed two below. Collection descends into
the worktree, every module basename appears twice, and pytest Interrupts.

The measurement is the interesting part: `136 tests collected, 19 errors`, exit
2, and the file it wrote holds the right 136 ids in the right order. The output
is not merely plausible, it is exactly correct. `grep :: | sort` discards the
exit code, so `diff` reports no change and is telling the truth about two files
that are both right. Only the exit status separates a good run from an aborted
one here, and the recipe's own `wc -l` guard checks length.

`collect_diff_gate` executed that command on every verify and passed, asking
`len(collected) > 0` — the same question the `wc` line asks, in a second home.
So the repository's empty-scope rule arrived inside the gate written to enforce
it. node-zero's framing is the general statement and it is the workspace's
two-consumers rule one level up, applied to a procedure and its own safety
check rather than to two pieces of code:

> The guidance and the guard were written by the same author, so the guard was
> written against the failure the author imagined rather than the one the
> guidance causes.

**Any recipe that ships with a guard should have the guard written against what
the recipe does, not against what could go wrong in general.** Scoping to
`tests/` removes the cause; checking the exit code covers both the aborted case
and the empty case the length check was written for, so it strictly dominates
what it replaces. The recipe now announces its own failure, and the gate
requires the announcement to be absent — then strips the scope back out and
requires it to be present, because the first assertion alone is a negative over
a set nobody sized, which is the reading that shipped.

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

### When a `VERSION` file is wrong, which is more often than this section implies

The template ships one and **skeletor itself refuses one**, and until sky.boss
asked, nothing wrote down what separates the two. The condition is narrow and it
decides the whole question: *does anything install this?*

A published artifact has a declared version — in a package index, a Docker tag,
a wheel — and that declaration has to live in a tracked file, because the thing
being installed is a tarball with no git history in it. `VERSION` is then not a
copy of the tag; it is the primary, with a single writer (Release Please) that
also moves the tag, which is what makes it a generated artifact rather than a
second home.

Nothing installs skeletor, and nothing installs a repository whose only entry
point is a wrapper script beside the source. There the tag is the only version
anybody can observe, `git describe` reads it, and a tracked `VERSION` is exactly
the duplicate this project refuses everywhere else — with the worse property
that a rebase or a hand-edit can make the two disagree while both look right.

So: **take Release Please when the project is published, and `git describe` when
it is run from a checkout.** A tree that guesses wrong is cheap to correct in
either direction, and the badge section below is downstream of the same fact —
it says "a third home for a number whose first two are the git tag and
`VERSION`", and for an uninstalled project the second of those should not exist.

#### The flag, and the shape a flag gets here

`--versioning tag|release-please` is the one install-time flag that changes what
ships, and it took a long time to build because the shape mattered more than the
feature. **A flag may subtract a file set. It may never reconfigure one.** The
scaffold is this repository's only test, so every mode multiplies the
verification grid; a mode that wrote files *differently* would need a grid this
project cannot afford, and it would push a conditional into every document
describing the workflow — which is how `CONTRIBUTING.md` and the README setup
block would end up generated.

So `tag` removes four paths and changes nothing else. What that leaves behind is
the interesting part: prose. Subtraction alone produces a `## Releases` heading
with nothing under it, which is *worse* than the wrong paragraph, because the
`tag` mode does have a release procedure — `git tag -a`, the one this repository
uses on itself. `<!-- SCAFFOLD-IF <path> -->` and its inverse ship the true half
of each alternative, keyed on whether the path arrived rather than on the flag.
Keying on the flag is the version that rots: a renamed overlay or a new mode
keeps prose about a directory nobody shipped, and no gate can tell, because the
paths still resolve in the configuration the author happened to be looking at.

That mechanism was not designed for this. It was one hard-coded `.claude/` case,
written the same afternoon because the tier-composition gate caught `--agent
none` shipping an index that routed readers to three paths inside a directory
that flag exists to remove. `--versioning` is what showed it was general.

And the flag validates itself, because the composition gate reads its axes out
of `bin/skeletor-new`: adding `VERSIONING` to that map put every `tag`
configuration into a grid of 36 on the next run, with no gate edited to admit
it. It immediately found the two files that name the Release Please config in
order to *handle its absence* — a `[ ! -f ]` test and a guarded `Path`. To a
predicate over paths those look exactly like a dangling citation, and the
difference is the entire finding, so the files declare which they are at the
site with `SCAFFOLD-OPTIONAL`, checked for staleness in both directions. Two
entries, both of them about the notation rather than about code the predicate
mis-shaped, which is the line this repository already draws.

### Badges

Two, and only when `--org` names a real owner. Neither one *stores* a value,
which is the whole constraint: a hard-coded `version-0.1.0` badge would be a
third home for a number whose first two are the git tag and `VERSION`, and
Release Please bumps both without ever touching the README — correct until the
first release, wrong forever after. The release badge is instead a *view* of the
latest GitHub release, the same tag `get_version()` reads through `git
describe`. There is nothing to keep in sync because there is no copy.

The CI badge is pinned to `--release-branch` and labelled for it, and it changes
what the badge claims: not "is the trunk green" but "is the last release green."
A bare workflow badge reports the repository's **default** branch — the
`--base-branch` that `skeletor-new` creates with `git init -b` — and that is a
different question. A badge is read by somebody deciding whether to depend on
this, so it should answer the released one.

That is the reason today. It is **not** the reason the pin was introduced, and
the difference is the point of recording it here. `ci.yml` used to run on `push`
for the release branch alone, so an unpinned badge read "no status" for the life
of a perfectly healthy project — the pin was a workaround for a defect one file
away. proto.pilot, scaffolding into a real repository, found what that trigger
actually cost: a project that commits straight to its base branch, which every
project does while it is one person, ran no CI at all, and three commits landed
before anybody noticed, because "no workflow ran" and "the workflow passed" are
the same absence of red. The base branch is in the `push` trigger now.

So the defect is gone and the conclusion survived — which is the case worth
naming, because nothing goes red when it happens and nobody re-reads the reason.
The tell is a reason phrased as a **workaround** rather than an **intention**:
"pinned because the badge would otherwise read no-status" names a broken thing
and therefore has an expiry date nobody wrote down, while "pinned because a
badge is a claim about what was released" survives any fix anywhere. When you
close a defect, the rules justified *by* it are now justified by nothing — and
they will not tell you. Go and re-read them.

The semantic half of that cannot be a test: nothing can read "because X is broken"
and go check whether X still is. The mechanical cousin can, and the scaffold now
ships it — `tests/test_docs_name_live_code.py` fails when a reference doc names a
callable the tree used to define. It came from proto.pilot, which built it after
this exchange and found the useful predicate on the second attempt: "every
backticked call must resolve" flagged four correct references out of five, and a
gate needing four exemptions on its first run is describing the wrong shape.
Asking git instead — did this repository ever define that name — has no
exemptions at all.

That rule is stated elsewhere in this repository as *five* things, and the
discrepancy is the point: **the count was never the load-bearing part.** sky.boss
supplied the discriminator, from a doc-link gate of its own. What an exemption is
*about* is the tell:

* An entry about **code the predicate mis-shaped** means the predicate is wrong.
  Four correct references flagged out of five is a matcher describing the wrong
  shape, and the fix is a tighter predicate. jam.sense's ledger detector took the
  same correction — five false positives, answered by requiring the `try` to sit
  in a loop over `.splitlines()` *and* its function to call `read_text`, which
  left its `ALLOWED` map empty.
* An entry about **the convention's own vocabulary** cannot be predicated away,
  because what is excluded is prose *about* the notation: the sentence that
  defines `[[slug]]` cannot resolve a slug, and a dated record of a rename names
  the dead name on purpose — resolving it would mean the rename had not happened.
  Two of those are not four of the first kind.

Where a structural marker separates the two, it beats both. This template hit the
vocabulary problem head-on in `test_docs_name_real_commands.py`: prose names
commands that do not exist in three distinct ways, all indistinguishable to a
matcher. Scoping to fenced ```bash blocks removed all three at once, because a
fence is the difference between *describing* a command and *telling you to run
it*. Zero exemptions, measured on a real tree rather than assumed.

And whatever the kind, the entry is checked against what it describes on every
run — see the allowlist staleness rule in `CLAUDE.md`. A reason makes an
exemption a decision; only a check keeps the decision true.

### The cost of the rule that every rule carries its reason

This document's first principle manufactures the artifact class that is hardest
to keep true. **A claim in a docstring or a comment is the least-checked prose in
a repository**: it reads as already verified, so nobody re-derives it, and
nothing recomputes it. Three of the six defects found on 2026-09-01 were code
contradicting a comment sitting directly above it, and all three yielded to the
same method — somebody ran the thing — and to no amount of reading.

- `bin/skeletor-verify`'s actionlint gate gave its reason as "the tree has no
  actionlint hook", two sentences from a note saying such a hook would be a good
  change. A reason with its own trigger on the same page.
- `pristine_post_copy` existed because the manifest had recorded something no
  render produces, and held a second literal copy of the post-copy sequence — the
  duplication sitting inside the apology for that duplication's consequence.
- A comment in `ci.yml` claimed a malformed `pyproject.toml` fails the step
  loudly. The first run showed it printing a traceback and carrying on to install
  the wrong thing; it is true only under a shell that sets `-e`, which GitHub
  happens to provide. A guarantee that holds by accident reads exactly like one
  that holds by design.

The remedy is not fewer comments — the rule earns its place, and the alternative
is rules nobody can evaluate. It is to keep two kinds of claim apart:

- **Why something is done** is a judgement. No machine checks it, it does not
  rot on its own, and writing it down is the whole point.
- **What the code does** is a fact, and a fact in a comment is a *test that never
  runs*. Either check it — `test_lint_tool_parity.py` and the manifest
  cross-check are both a comment somebody turned into an assertion — or run the
  thing and say what the answer depended on.

The third example is the one to remember, because it is the hardest class: it was
not "nobody ran it". It was run, it disagreed, and believing the comment would
have cost nothing until the day a default changed somewhere else. Say what a
claim depends on, and it stops being a coincidence you are relying on.

**Not every fact should be promoted, and the split is now-versus-always.** An
invariant — these two files pin the same version, every `script()` names a file
that exists, this allowlist holds no stale entries — is checkable forever, and an
assertion is its right home. A *contingent* fact is not: proto.pilot's dead-symbol
check excludes `NOTES.md` by role and observes that the exclusion exempts nothing
today, which is true and is expected to stop being true, because that file is
meant to eventually name a removed symbol. Asserting it would build a gate that
goes red the day the thing it guards starts working — the inverse of a ratchet,
and a worse failure than the comment it replaced. The honest form for a
contingent fact is what that one has: a dated observation, stated as an
observation. Same discipline as separating a perishable reason from a durable
one, and it resists being made into a rule for the same reason — telling the two
apart is a judgement about what the claim is *for*.

**And "in the file that states it" is a clause with a condition on it.** The
invariant reads as universal and is not. Co-location assumes a reader arrives at
the artifact and reads outward, which holds when a reason explains exactly one
thing — one gate, one guard, one function. It inverts when the reason explains
*several*, and the workspace this shell came from says so in almost opposite
words: **a rule that exists only as a comment in the producing repo is
unreachable from where the mistake gets made.** The mistake happens in the
consuming repo, so the reason belongs at the seam. And a reason for an
**absence** — why something is deliberately not done — has nothing to sit beside
at all, which is what a plan's `## Dropped, and why` section exists to hold.

So: co-location beats a home-of-its-own when the reason has exactly one owner.
When it has several, or none, it needs its own home and a route to it. That is
why this document exists rather than being distributed into the files it
describes.

The failure to watch for is not misplacement, and it would be found late. It is
that "it belongs beside the code" becomes a reason not to write the reason down
**at all** when no single file obviously owns it — the seam doc that nothing owns
never gets written, and the symptom is an absence. Nothing goes red on an
absence, which is this document's other recurring sentence arriving from a third
direction.

Worth recording how that narrowing was reached, because the method is the
transferable part: the co-location rule was applied three times in one day and
won three times, and the two of us then asked whether three-for-three was a rule
or a shared blind spot. All three cases were 1:1 — the regime where it is
easiest — so the streak was evidence for one clause and no evidence at all about
the other. **A rule tested only where it is easy has a boundary you have not
found yet**, and the way to find it is to ask what regime the tests were all in.

The other half of what made all three findable is not a rule at all, and cannot
be turned into one here: a second person naming the shape while somebody happened
to be looking at the right file. A rule on the wall is not a check. It is a thing
you agree with while doing something else.

This paragraph is itself the second instance. The reason was fixed in
`badges()` and in `CLAUDE.md` within a minute of the trigger change, and stood
stale here for an hour, in the document [`CLAUDE.md`](../CLAUDE.md) calls *the
evidence* — the widest-audience copy, and the one nobody was looking at. The
distance that hides a stale reason is not measured in files. It is measured in
audiences: each copy has its own reader, and you update the copy whose reader
you are at the time.

`--org` defaults to `OWNER`, which names no repository, so the default scaffold
ships no badges rather than opening every README with a broken image — the
cosmetic form of shipping a gate that is red on arrival.

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
