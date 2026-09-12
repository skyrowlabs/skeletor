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

### A reason written when a job is *placed* is what makes an unrelated change auditable

The `FULL-SUITE-BECAUSE:` markers on `lint`, `integration` and `ui` exist so a
job gated on `full_suite` has to say why it can afford to sit out a pull
request. That is a claim about the job. What was not anticipated is what the
claim is worth **later**, when something the job's author never saw changes the
condition underneath it.

`ecf1029` changed how `docs-only.cjs` classifies and moved `full_suite` alone.
Six adopters had to work out what that cost them, and the answers ranged from
*five jobs to one* to *nothing at all* — the same commit, different trees.
Nobody could answer it centrally, because the cost is a fact about which of a
tree's gates are duplicated elsewhere and which of its suites are empty. What
made it answerable **per tree**, in minutes, was that each job carried a written
reason that could be tested against that tree:

    lint          "every gate also runs in the pre-commit hooks and in `dd check pre-push`"
                                                      TRUE here — all four
    integration   "needs the stack up and seeded"      collects 0 tests here
    ui            "it drives a user interface"         collects 0 tests here

The marker turns *is this change safe?* — unanswerable — into *is each of these
three sentences true in my tree?*, which anybody can check.

**The stronger evidence is a job that was placed on the other condition.** When
the node steps were split out of `lint` into their own job, the proposal was to
gate it on `full_suite` like the job it came from. dream-doll argued it belonged
with `unit-tests` on `docs_only`, because the node job is *the product's own
suite*. That was an argument about a job which did not yet exist, settled on a
principle rather than on a consequence — and the consequence arrived two
releases later:

> Had the node job shipped on `full_suite`, this release would have silently
> stopped running eslint, typecheck, vitest and the build on every pull
> request — and nothing would have gone red.

So the rule is not merely that a gated job should explain itself. It is that
**the condition a job is placed on is a decision with a blast radius nobody can
see at the time**, and the only thing that makes it reviewable afterwards is
having written down which question the job answers. Every gate that touches the
product sits behind `docs_only`; `full_suite` is for gates whose absence is
recoverable. Placing a job is choosing which of those it is.

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


### A sibling's fix does not notify the tree it was made for

The contrast above has a third case, and neither half of it covers this one.
Invariant 7 asks whether a sentence is true in the reader's tree at the moment it
is read, and it catches the sentence that was *never* true there — a guarantee
implemented by rendering, a count measured in one tier. It is silent on a
sentence that was true when written and **stopped** being true because somebody
else fixed something.

The instance is sky.boss's, and it cost this repository a reordered backlog.
Their `CLAUDE.md` warned that a `cli/` on `sys.path` broke a named sibling's CLI.
jam.sense had closed that months earlier — `-P` on both exec lines of their
wrapper, with a comment citing sky.boss's repository by name and the issue number
as the reason — and nothing in sky.boss's tree changed, because nothing could.
**The fix landed in the repository that had the bug; the warning lived in the
repository that had caused it.** Measured, when it finally mattered:

```
jam --help from /tmp        exit=0
jam --help from sky-boss    exit=0
```

The named victim was immune, and the document naming it had said otherwise for
months. They relayed that sentence to me as load-bearing, and I reordered a
backlog on it without running the one command that refutes it; both were
retracted the same evening. The reordering is the measure of the class rather
than an aside, because **a warning about a hazard somebody has already fixed
reads as more credible the longer it sits** — it ages into settled knowledge
without ever being re-checked, and the citation-by-name that makes it persuasive
is exactly what makes it unfalsifiable from inside the tree holding it.

The general shape sky.boss named: *a true statement about a system whose state is
owned somewhere the file cannot see.* The workspace already records the easier
direction — a note about a neighbour's **pending** work becomes false the moment
that repo does the work. This is the same sentence about **completed** work,
which is harder in both directions: nothing fires, and the claim gets more
authoritative rather than more suspect.

**Why it belongs in this document specifically.** A scaffolded tree is dense with
present-tense claims about machinery in repositories its reader does not own —
what GitHub Actions permits, what `pre-commit` does on a hook, what a sibling
tool puts on `sys.path`. Every one of them is a sentence whose truth is
maintained by a third party with no obligation to this tree and no channel into
it. The template cannot hold those to invariant 7, because invariant 7's test is
*is this true in the reader's tree*, and the reader's tree is not where the
answer lives.

**It ships no gate, and that is the finding rather than a gap in it.** The
enrolment would be "a sentence about somebody else's software", which is not a
predicate; the requirement would be "re-verify it", which nothing local can
perform. This is the same drawer as `can_approve_pull_request_reviews` — a fact
about the account rather than the tree — and it takes the same remedy this
repository already uses there: write the limit down where a reader meets it,
rather than pretend an instrument covers it. What the writing rule adds is
cheaper and available at the point of authorship:

> **A claim about a neighbouring repository carries the command that checks it,
> or it is not made.** `jam --help from sky-boss → exit=0` is one line, ages
> honestly, and converts a belief into something the next reader can re-run in a
> second. A prose warning that names a victim converts a belief into a
> reputation.

The narrower lesson for peer traffic is mine, not theirs: **a relayed claim gets
one command before it is allowed to reorder anything.** I had a checkout of the
tree the claim was about and did not use it — which is the fifth instance that
evening, between three sessions, of somebody reasoning off a document where the
mechanism was one command away. sky.boss's own summary of their half is the line
worth keeping beside it: naming a failure mode does not immunise you against it,
and they produced theirs in the same message where they corrected me for its
cousin.


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

#### The same flag, thirteen days later, one artifact over

That fix corrected how the toolchain is **documented** — `setup_commands()` —
and left the toolchain's own **config** in the overlay the argument above had
just shown was the wrong home. `.flake8`, `pyproject.toml` and
`pyrightconfig.json` stayed in `template/python/` while the source they govern
shipped at `core`.

So a `--language node` tree arrived with 52 python files and nothing configured
to read them, and three things followed:

- `cli/check.py` runs each linter only when its config exists. With both python
  configs absent it ran eslint alone and printed `✅ all 1 gates passed` — the
  "worked fine, told nobody" shape, where **the absence of a config reads as the
  absence of a language.** Green, over 52 unread files.
- The pyright hook's entry is `pyright --project pyrightconfig.json`, so
  `pre-commit run --all-files` — the first command the README gives a new user —
  could not pass. Invariant 5, in the tier that is documented as *take this
  always*.
- `tests/test_marker_coverage.py` reads `pyproject.toml` unconditionally and
  raised `FileNotFoundError`. That file's own comment says *keep this block in
  sync with tests/pytest.ini* — a documented sync pair whose two halves shipped
  at **different overlays**, which is stash.flow's tier-composition class with
  the axis changed from tier to language.

**Why the paragraph above did not prevent it.** It is filed as a fact about
`setup_commands()`, and the sentence that generalises it says to check a flag
against *what the tiers actually ship*. Nobody re-ran that check when the
subject was a config file rather than a documented command, because the finding
had a fix attached and a fixed thing reads as a closed thing. Naming a failure
mode does not immunise you against it — this repository has said so once
already, about a completeness claim written in the hour after committing a fix
for exactly that sentence.

**Why no gate here saw it.** `bin/skeletor-verify` sets
`gated_language = "python"`: every language is scaffolded, so an unrendered
placeholder in the node overlay is still caught, and only the python trees have
their own suites executed. The question "does this configuration ship a linter
for the source it ships" is therefore invisible in exactly the configurations
where the answer was no. It took dream-doll, the first `--language node`
adopter, to find it — which is the founding rule of this file arriving on the
language axis: **a tree only ever knows its own configuration, and the
generator's question is the one across all of them.**

`unlinted_source_gate` asks it directly, for every `--language` the parser
offers rather than the one the grid executes. It reads `LANGUAGE_CONFIGS` out
of the generated `cli/check.py`, so a fourth linter added there is covered on
the next run. Reverting the move turns it red on `node` and on `none` and green
on `python` and `both`, which is the tier signature the defect predicts.

`--language none` is worth its own line: it was equally broken and it is **not
in `configurations()`**, because that helper enumerates `LANGUAGE_OVERLAYS` and
`none` ships no overlay to enumerate. A documented choice that the composition
gate cannot see is the registry hazard wearing the shape of an absence.

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


### The instrument built to tolerate the thing it was detecting

A third face of the same rule, and it arrived as a bug report against this
repository that turned out not to exist.

stash.flow reported that `skeletor-upgrade --json` puts prose on stdout, so an
envelope cannot be piped. Answering it took a hand audit of every
`subprocess.run` in the tool and four measured paths, and it did not reproduce:
stdout carries the envelope alone on all of them, `detail()` is
`file=sys.stderr`, and every child process captures. They found their own cause
in one move and stated it better than the finding:

```
concluded from:   … --json $T 2>&1 | json.load(sys.stdin)
                                ^^^^ merged stderr INTO stdout
"confirmed" by:   … --json $T 2>/dev/null | t=read(); json.loads(t[t.find('{'):])
                                                             ^^^^^^^^^ tolerates a prefix either way
```

> **A lenient parser cannot disconfirm the claim that parsing fails.**

Where a plant that does not land means the instrument could not *reach* the
defect, this is an instrument that could not *notice* it — and the tell is the
one worth carrying, because it is not carelessness: **the lenient step felt like
robustness.** `find('{')` is what a careful person writes. So the rule has a
positive form now: when a check exists to detect malformed input, every
tolerance in the checker is a place the answer can come from.

**The hole it exposed was real and is the one that cost the hour.** The template
ships `tests/test_output_contract.py`, which asserts stdout-parses and
stderr-speaks over every `scripts/check_*.py` in a generated tree — and nothing
had ever asked it of skeletor's own tools. That is this repository's recurring
failure, a rule shipped to everybody and not applied here, and it is why the
answer had to be assembled by hand instead of read off a green check.
`check_upgrade_json_is_pure` now runs it on every scaffolded tree across three
paths, the `manifest-drift` refusal included, since a non-zero exit is when a
consumer is most likely to be parsing.

It is the **second** gate here that cannot use `run()`, for the same reason as
the pyright one: `run()` merges the streams, and stream separation is the whole
question, so a gate built on it would report the contract satisfied by
construction. `subprocess_env()` was split out of `run()` so that "cannot use
`run()`" does not also mean "builds its own environment and drops the git
identity", which is the forgetting `run()`'s own comment warns about, one level
up.

**A withdrawn finding that leaves a standing check behind is worth more than a
confirmed one that does not.**

A fourth face, from the same peer the same night, and it is the cheapest to
miss because nothing is written to a file. They pre-registered a prediction
about an upgrade — good practice, and the habit this document already
recommends — pinned to `origin/main`. The tag was one commit away, so the
prediction was about whatever that ref happened to be at read time.

They had argued that morning against storing a "last checked at" field in the
manifest, on the grounds that *am I current* is not a fact about a tree but
about its relationship to a moving target, so such a field is stale on write.
Their own statement of the repeat:

> **The "am I current" asymmetry applies to claims, not only to fields.** A
> claim whose subject is named by a moving ref goes stale exactly the way the
> field would, and it is harder to see because nothing was written to a file.

The reason it does not feel like the same mistake is that a ref reads as *a
place you are looking* rather than *a value you are recording* — and a
prediction is a recorded value. Pin a stated expectation to an immutable ref, or
it is not falsifiable by the time anybody checks it.

### The path that could not say where it came from

`state_dir()` resolved `os.environ.get(STATE_ROOT_ENV) or STATE_ROOT_DEFAULT` and
returned a `Path`, which is correct and **cannot say which of the two answered**.
jam.sense spent an investigation on a broken pane whose entire answer was *the
variable was not exported in this context, so the default answered* — and the
default had moved one release earlier. One field would have closed it in a line.

`state_root()` returns `(path, source)` and `state_dir()` goes through it. The
`source` is reported and never acted on: a caller that behaved differently
depending on how the root was found would have made the override mean two
things.

**The test for it shipped as a tautology first, and a plant said so.** The
obvious assertion is to set the variable and require
`state_dir(...) == state_root().path / ...` — which passes under a *split*
resolver, because two independent lookups of one environment agree. Planting the
pre-change code, which reads the environment separately, came back green on
exactly the test written to forbid it.

Two copies of a mistake agree with each other, which is this document's oldest
lesson arriving inside a five-line test. The assertion is structural now:
replace `state_root` and require the path to follow. Nothing but a call can do
that, and the plant that was green is red.


### A report and its remedy can share a root

Three peers sent reports in one night, each with a proposed fix, and all three
fixes were withdrawn by their authors while all three findings held. That ratio
is not a coincidence about those three.

- sky.boss: a real defect in `skeletor-components`, with a discriminator the
  tool's own docstring already refutes.
- stash.flow: a real question about `--json`, with the instrument above.
- jam.sense: a real finding — no estate-wide vintage view — proposing a sibling
  glob in `skeletor-maintain`, which would bake this workspace's parent
  directory into a tool other people run. **That is the v0.9.0 defect they had
  come to report, one level up**, and green over zero siblings is not a passing
  check but an absent one, which is this repository's empty-set rule.

Their own statement of it is the general one:

> The report and the bad recommendation had the same root.

A remedy proposed from inside a blind spot inherits the blind spot, and it
arrives carrying the authority of somebody who has just been right — which is
precisely when nobody checks it. So **a report and its patch are evaluated
separately even when the report is correct**, and the finder being right about
the defect is not evidence about the fix.


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

`bin/skeletor-verify` gates it now, because inspection found this one and
nothing stopped the next. **The homogeneity that hid it would equally hide a bad
fix** — in a tree under `~/skyrow.labs` a correct substitution and a hardcoded
literal produce the same string, so verifying there is vacuous, and the outside
coordinate has to be manufactured. `author_leak_gate` derives who this checkout
belongs to from the machine and the remote — the directories above it, the home
directory's name, `origin`'s owner, the committer's email — and asserts a
rendered tree contains none of them. A population, not a list of the leaks
somebody already found; comparison on alphanumerics only, so `skyrow.labs`,
`skyrow-labs` and `skyrowlabs` are one token. `GENERIC_PATH_WORDS` is the
definition of that population rather than an exemption from it: `runner` and
`work` are in it because GitHub checks out to `/home/runner/work/<repo>/<repo>`
and would otherwise supply two tokens that appear in any tree mentioning
Actions.

Two things it is careful about, both this repository's own rules. It refuses to
run on an empty token set instead of passing — a scan for nothing is green and
worth nothing — and it plants in **both** directions, requiring the detector to
find a synthetic leak and to stay silent on text naming nobody, because a
normaliser that stripped too much would match everything and pass the first
check alone. And it does not claim initials: `SL_AGENT_LOGS` leaked the same
organisation in a form no derivation produces without guessing, and a gate that
guessed would be a list wearing a pattern's clothes. That half is closed by the
fix, and saying so beats implying otherwise.

Two second homes came out with it. The test's `ROOT_TOKENS` was a literal
`r"sl-agent-logs|SL_AGENT_LOGS"` — the second definition this test exists to
forbid, wearing the costume of the test that forbids it, and failing in the
reassuring direction: rename the root and the pattern matches nothing, so the
check goes green over a tree full of stale copies. It is read out of the
resolver now. And `AGENTS.md`'s Rule 14 stated the path in prose, which
`test_state_paths.py` cannot see because it scans `cli/` and `scripts/` for
Python. The rule forbidding a second definition of the path contained one; it
names `state_dir()` and tells the reader to ask it.

### The record was right and the report was not

`skeletor-components report` said `⬆️ scripts/paths.py — upstream moved since
v0.7.0; this copy is untouched` about a file sky.boss had cut from 159 lines to
63 **before recording it**. `local_sha` is captured at `record` time, so it
baselines whatever the file was at that moment: edit-then-record and take-as-is
are indistinguishable from then on, permanently. The sentence is accurate about
what the hash measures and wrong about what a reader takes from it.

It is not an edge case. **Adoption is when nearly all forking happens** — you
take a file, cut what does not apply, record — so the blind case is the common
one. It reproduces in jam.sense at a different ref for a different adopter, with
two of three "untouched" lines false, and the row worth fixing first is the
green one: a fork rendering as `✅ current` is the same false claim on a line a
reader skimming for `⬆️` never stops at.

The consequence compounds in the costly direction. On a fork, *"upstream moved"*
usually means *check whether the change even applies to what you kept* — and
sky.boss's `paths.py` was the state-root fix, which they had already answered by
**deleting** the block rather than re-defaulting it. A reader trusting
"untouched" pulls back in the thing they removed on purpose.

**The obvious repair is unsound, and the tool's own docstring already said so.**
`source_sha != local_sha` at record time looks like the fork signal and is not:
`source_sha` is raw template and `local_sha` is the adapted copy, so the two
differ for every file carrying a `{{...}}` placeholder however faithfully it was
taken. `scripts/paths.py` has two. Adopting that rule reports a fork for every
verbatim take of a templated file — the same false reading facing the other way,
and harder to doubt, because it fires on real forks too.

So the first half of the fix is words, and only words: every sentence says
**"since you recorded it"**, which is exactly what the comparison measures.

The second half is what survives the retraction, and sky.boss found it in the
same message they withdrew the general rule: **hashes cannot tell a fork from a
rendering because rendering and editing are the same signal — but for a file the
scaffolder does not transform, they are not.** A template file with no `{{`
substitution and no `SCAFFOLD-IF` block is copied byte for byte, so
`source_sha != local_sha` at record time can only mean somebody changed it. That
fork is *provable*, needs no schema change, and is computed from what the
manifest already holds.

It is deliberately partial and says so by silence. Of the four files a hash
comparison flags in sky.boss's tree, three are real forks and one is rendering —
and the three are exactly the ones with nothing to render. Everything else stays
undetermined rather than reassuring, which is the direction the original defect
ran the wrong way.

`TRANSFORMS` is read from what `bin/skeletor-new` actually does rather than
guessed, because a new transform must not make this quietly wrong: it would have
to be added here to be missed, instead of merely forgotten. And the gate asserts
**both** directions in one fixture — the truncated placeholder-free file named,
the fourteen-placeholder file left alone — because a rule that only ever fires is
being agreed with rather than applied. `docs/rules/commits.md` is in that fixture
precisely because it is the counter-example that killed the general version.

sky.boss named the class, and it is the one this document has been accumulating
all round: **the record was right and the report was not.** `--force` recorded
its overwrites correctly and printed them after the write; `--ported` performed
or skipped the advance correctly and announced it unconditionally; the currency
verdict computed correctly and was gated out of existence. Four instances, one
shape — *the artifact is sound and the sentence about it is not* — which is
worth more than any of them individually, because it says where to look next in
a tool whose entire product is a report.

### The justification travelled to the other door and the mechanism did not

`bin/skeletor-upgrade` has refused a dirty base since `5230a7c`, because a
manifest naming a render that exists in no commit poisons every later run.
`bin/skeletor-new` — **the door that creates that manifest** — had no such guard
at all.

`reaches_a_render`'s own docstring gave the reason away, and nobody read it that
way for four tags: it called its scoping *"the one already accepted for the
scaffold end of the same pipe."* The argument came from the scaffold end. The
code never went there. That is this repository's recurring failure — the
argument standing in for the mechanism — one file over from where it was last
retracted.

stash.flow reproduced every property, and the ordering of severity is theirs:

- **The upgrade refuses before writing; the scaffold writes first**, and the
  adopter commits the result in their own first commit.
- **The upgrade's damage is a wasted run; the scaffold's is a file in somebody
  else's git history.**
- **The untracked case records a clean ref.** `git describe --dirty` is
  untracked-blind, so a file under `template/` renders into the tree, is
  recorded in the manifest, and leaves the ref looking ordinary. `cross_check`
  then refuses every later upgrade, permanently, in a different tree for a
  different person, and `--repair-manifest` fixes the symptom without the cause
  ever surfacing.

The blast radius is bounded and safely so, which they also measured:
`copy_overlay` selects overlays while `reaches_a_render` says `template/` wide,
so the predicate warns on strictly more than can poison. Conservative in the
right direction, and no reason to narrow it.

**The repair is not "add a warning", and that is the part worth keeping.** A
warning keyed on `git describe --dirty` would reproduce the defect this
repository had just fixed one door over — same wrong predicate, one release
later, in the file that *writes* the record instead of the one that reads it.
`render_dirt()` is the term at both ends, and it now lives in
`bin/render_guard.py` so there is one predicate rather than an agreement between
two. That module is itself a render input, because editing it changes which dirt
counts.

Two halves ship together because each is what makes the other survivable.
`skeletor_ref()` stamps `-dirty` whenever `render_dirt()` finds anything,
whatever git thinks — its docstring had claimed *"a dirty tree is recorded as
dirty and warned about"*, and stash.flow measured **both clauses false**, with
the compounding that matters: the missing warning alone costs a puzzled minute,
and it cost a manifest only because the recording missed exactly the case that
does the damage.

> **When a false clause is load-bearing for a second false clause, fixing the
> cosmetic one first leaves the failure intact and looks like progress.**

`--allow-dirty` rather than a warning, because a warning is the right answer
where nothing is recorded and everything here is recorded. `bin/skeletor-verify`
passes it at every site that scaffolds from this working checkout, which is
honest rather than a workaround: those trees are throwaway, and that is the one
caller for which an unreproducible base costs nothing. The upgrade's internal
render passes it too — it has made its own ruling by then — and appends the flag
only when the checkout being rendered from knows it, so an older scaffolder is
never handed an argument it cannot parse.

The gate's third assertion is the one that makes the other two worth having:
refusing is easy to satisfy, and the property that actually cost a manifest is
that `--allow-dirty` leaves a **trace** rather than a silence. Each assertion was
established by planting its own defect, and removing the honest-ref half turns
that one red while the refusal stays green.

One consequence caught by the grid rather than by reasoning: fixing the ref
**moved which configuration discriminates** in `dirty_signals_gate`. Its
envelope assertion had been keyed on an untracked template file producing a
clean ref beside a real hazard; the moment the ref became honest, that assertion
was asserting the bug. It is keyed on the two fields answering different
questions now — a tracked edit outside the render still sets git's repo-wide
suffix while `render_dirt` is empty. **A gate keyed on a symptom expires when
the symptom does, and it expires by going red on the fix**, which is the good
direction and still a warning about how it was written.

### Standing state counted as work, and the verdict that cannot fail later

Two findings against the same block, from two trees, and both are about a
sentence rather than a computation.

**A standing decline suppressed the currency verdict, permanently.** The test
for *nothing to carry over* read `any((added, updated, merged, conflicted,
collided, declined, dropped))`, and the last two are standing state by
construction: a file you deleted is not restored, a file the template stopped
shipping is not removed, and both are reported on every run for ever. So an
adopter carrying one **never saw "already current"** — not on that release and
not on any future one.

The tree that most needs the sentence is exactly the tree that could not receive
it. mind.head's manifest will read `v0.9.0` indefinitely, because the manifest
is re-copied only by a run that applies something; the sentence beneath the
verdict exists to say so, and to let them tell *"I upgraded and there was
nothing in it"* from *"I never ran the upgrade"*. Four permanent declines from a
toolchain swap made that distinction unreachable. They reported it with a
control — same render, same upgrade, the declines the only difference, present
in one run and absent in the other.

**It is the `--ported` guard one release later**, and the mirror image: there the
term set was too small and excluded a conflict, here it is too large and
includes two things that are not work. Both make a true statement unreachable
for exactly the adopters it describes. The term is `fresh` now — the actionable
half of a decline, where the template has moved since — because a decline can
become news again and a drop cannot: nothing records that you were told.

**And "already current" from a dirty base reads as a conclusion, not a plan.**
stash.flow ran it against a base whose `bin/skeletor-new` — the thing that
renders `ours` — carried 17 uncommitted insertions. The dirty-base warning fires
and says *this plan includes them*, which is right about a plan and the wrong
shape for this line: it wears a ✅, the manifest note under it is stated as
settled fact, and the only signal that any of it is provisional is a `-dirty`
suffix inside a version string. They could only learn the answer was right by
cloning the tag and asking again.

Their reason for checking is the general one:

> **"Do nothing" is the only verdict that cannot fail later, so it is the one
> that has to be checked now.**

Every other verdict is tested by what happens next — a bad merge shows up, a
conflict stops you. This one has no next step to fail, so a wrong answer is
permanently invisible, and it is the answer a reader most wants to receive.

The verdict now says it is provisional when uncommitted content reaches the
render — and the first version of that fix got the predicate wrong in both
directions at once, which is the more useful half of the story.

It keyed on `head_ref.endswith("-dirty")`. `git describe --dirty` is
**untracked-blind and repo-wide**, which are precisely the two properties
`reaches_a_render` exists to remove — after one untracked `notes.md` at this
repository's root refused every adopter in a five-repository round — and it
walked straight back in through a version string. stash.flow measured both
rows: a tracked edit to `docs/`, unreadable by any render, printed *"includes
uncommitted template edits"* when there were none; an untracked file under
`template/`, which a render really does read, printed nothing at all — not even
the `-dirty` suffix this document had just called *the only signal that any of
it is provisional*.

> **The guard was derived from the text of the line rather than from the claim
> the line makes.** `head_ref` was already in that sentence, so reaching for it
> cost nothing and read as consistent.

That is the third condition-mismatch in three releases and the first with both
errors in one expression: too small in the `--ported` guard, too large in the
currency test, and here too small for untracked and too large for
outside-`template/` — because it answered *is this checkout modified* where the
question was *does unversioned content reach this render*.

**And the paragraph that stood here was wrong in a way worth leaving visible.**
It said the note was kept safe by the dirty-base refusal, and called that an
unstated dependency between two guards. There was no dependency: the refusal
used `reaches_a_render` and this line used `head_ref`, so the two could already
disagree, and stash.flow's second row is them disagreeing. An argument that two
mechanisms are coupled is not the same as their being coupled.

They are now. `render_dirt()` is the single predicate, and the note is
conditioned on `_WARNED_DIRTY` — the set the warning itself populated — so the
verdict cannot contradict the line three above it by construction rather than by
assertion. What the coupling buys is unchanged: a real run is refused, so a
provisional verdict can never be recorded.

The same finding carried a second one out with it. `warn_a_dirty_base` and
`refuse_a_dirty_base` hardcoded *"the base checkout"*, and **two different
checkouts reach them** — the recorded base, and the checkout that renders
`ours`, which are different trees whenever the base is a worktree at a tag.
node-zero printed the contradiction in one invocation: their dirty
`bin/skeletor-new` named as "the base checkout" three lines above a sentence
that had to say *"the checkout that rendered this"* in order to be true. Both
functions take a role now.

`dirty_signals_gate`'s third case is the only configuration in which a hardcoded
noun can be caught at all — base and renderer as genuinely different trees.
Every other gate here runs them as one directory, where a wrong name is
indistinguishable from a right one.

That paragraph originally closed with a stated limit, and the limit was wrong:
it said the pair *already current* **and** *provisional* was only reachable with
render-reaching dirt that changes no rendered byte, because an untracked file
under `template/` reaches the render by *adding* a file. `RENDER_INPUTS` matches
`template/` at its **root**, and the root is not an overlay source —
`copy_overlay` runs per overlay — so `template/ZZ_PLANT.md` is render-reaching
and renders nothing, and one `echo >` produces all three lines. stash.flow found
it by planting the case I had written off.

> **A documented limit is read as a fact about the tool.** That one was a fact
> about the fixture I had tried, and it would have discouraged exactly the plant
> that disproved it.

Which is the same shape as their own method note, and the reason it is kept:
their first attempt at that plant put the file at `template/` root **expecting
it to render**, and it rendered nothing — so a plant that lands out of scope is
indistinguishable from a plant that proves absence. The property that made it a
bad plant for their purpose is what makes it the right fixture for this one.

**And the predicate was replaced in the condition and left in the label.**
`head_ref` is the render's own `git describe --tags --always --dirty`, so its
`-dirty` still answers *is this checkout modified* — the untracked-blind,
repo-wide question this tool had just stopped asking — in the one line everybody
agrees reads as a settled conclusion, and in `--json` where a consumer filtering
on that suffix inherits both of the deleted guard's errors with nothing in the
envelope to say the predicate moved. The envelope carries `render_dirt` now: the
string answers *which version*, the list answers *does unversioned content reach
it*, and they are different questions that happened to share a spelling. The
human line names the case when the suffix appears without the hazard.

> **Deleting a guard from the condition does not delete it from the API.** The
> published field is where a replaced predicate keeps running.

### The scaffold's last word was an instruction to run the thing it had broken

`--force` into a repository somebody already works in — which `AGENTS.md` calls
*the usual case* — left all 105 rendered files **untracked**, and three of the
tests it had just shipped were red on arrival:

```
FAILED tests/test_docs_name_real_paths.py::test_the_scan_finds_the_citations
FAILED tests/test_setup_blocks_agree.py::test_the_scan_finds_blocks_to_compare
FAILED tests/test_setup_blocks_agree.py::test_the_shared_prefix_has_not_shrunk
```

Nothing is wrong with those tests. `tests/repo_files.py` enumerates with `git
ls-files` deliberately — a walk reads `.venv/.../pyright/dist/README.md` and
makes the verdict depend on what somebody's dependency tree happens to ship — so
in an untracked render the scanners find nothing and their empty-scope guards
fire, which is those guards working. `git add -A` in the tree turns three
failures into six passes, so the whole defect is one command.

The closing advice ends with `./<cli> check pre-push`. **The tool's last word
was an instruction to run the command it had just broken** — the same family as
the `--ported` sentence, where the message and the state disagree and the
message is the one the user acts on.

The fix stages what the scaffolder **produced**, and never commits: the commit
is the adopter's to make, the printed advice already says to read the diff
first, and staging is simply what makes `ls-files` answer. `git add -A` would
have been wrong in a way worth naming — it sweeps the user's own unstaged work
into a changeset labelled as skeletor's. The manifest already holds exactly the
right set. Files the adopter's own `.gitignore` excludes are reported rather
than forced in, because a template file invisible to every check that asks git
what exists is worth one line of output.

It survived four tags, and the reason is a near miss rather than neglect.
`--dry-run` shipped in `v0.9.0` and *looks* like it addressed this. It does not,
and node-zero drew the line: that flag is about **collisions at the moment of
writing**; this is about the render being **untracked afterwards**. Two moments
in one command, and the first one landing made the second look handled.

`adopted_repo_gate` is the first gate here to scaffold into an actual
repository, which is why nothing caught it: every other tree is generated into a
directory with no `.git`, where the scaffolder inits and commits and the
question cannot arise. Its second assertion is the load-bearing one — unstage,
and the same suites must go **red**. Without it the gate would pass on a tree
that was green for some other reason and would keep passing if the staging were
deleted.

The first version of that fix staged the manifest's `files` list, and **the
manifest is not in its own list.** It cannot be: `cross_check` is a bijection
between that list and the base render, and a hash of the manifest would have to
contain itself, so it sits beside the render by construction. An adopter who ran
`--force` and then did the obvious next thing committed 100 files and left
`.skeletor.json` — the one file `skeletor-upgrade` reads — outside git. A state
no existing adopter is in, and one where a tree is upgradable from birth except
that its base record is untracked.

That is the same class as recording post-copy mutations, facing the other way.
**"skeletor wrote this" and "the manifest lists this" are different sets**, and
using the second as a proxy for the first fails exactly where they differ. This
document already carried that pair once; it took a second instance in the
opposite direction to notice the proxy had been reached for again.

The gate could not see it either, and that is the more useful half. Its
assertion recomputed the tracked set from `produced` — two readings of one
expression, green whatever it said. It now also asks **git** what is left
untracked, which is the coordinate outside the scaffolder's own idea of what it
wrote, and planting the regression turns that assertion red while the original
stays green.

skyrow-workspace found it with one command against a real tree, and said the
thing worth keeping: reading the diff would not have shown it, **because the
code was correct about the set it named.**

Why it had never bitten: all four adopters have `.skeletor.json` tracked, and
**not because the tool tracked it.** Measured across the fleet, every one of
them scaffolded into a populated existing repository and a human ran `git add`
afterwards. *"All four have it tracked"* is not evidence about the tool; it is
evidence that four people did the same manual step. The defect was masked in
every tree that could have reported it, and stayed invisible until a run into a
repo where nobody tidied up — which is what `adopted_repo_gate` is.

The fix has a property the counts cannot show, and node-zero planted for it: an
unstaged `mine.txt` left in the target before scaffolding must stay out. **File
counts are identical whether or not `git add -A` was used, unless something
unstaged exists to be swept** — so both remedies proposed for this bug would
have co-opted an adopter's work-in-progress into a commit labelled as the
scaffold's, and the verification of either would have looked the same.

### A formatter is a second author with commit rights and no changelog

mind.head's only conflict taking `v0.9.0` was **one blank line** between two
imports, placed by `ruff check --fix` during adoption. They never decided it and
did not know it was there; `v0.9.0` rewrote the import immediately below it, the
two edits were adjacent, and the merge refused.

That is the third size of the collision class in three trees — a five-line
comment, a single `#:` separator, one blank line — and the smallest one breaks
the guidance shipped for the other two. *Audit per line* is correct and it is
not sufficient, because **the population an adopter is asked to inspect is not
the population they wrote.** No amount of care about where you put your own
comment reaches a line a program put there.

The counterfactual was measured in their tree and reproduced here: the merge as
shipped conflicts, and the merge with both **rendered** sides run through their
formatter is clean and correct. Reproducing it took one correction worth
recording — the divergence has to be *produced by the adopter's own formatter
config*, not planted by hand. A hand-planted line that the tree's formatter
would remove is the opposite case, and normalising correctly fails to match it.
The first version of this repository's gate planted the line by hand and proved
nothing.

The result is stronger than a smaller conflict count. `normalise(base)` came out
byte-identical to the user's file, so the classification is not "merged
cleanly" but **"never touched"** — there is nothing to merge at all.

Two objections had held this back and both were checkable rather than
arguable:

- *A tree-supplied command is a new trust boundary.* **False as stated.** The
  upgrade already runs the target's own `scripts/docs/regen.py` as a subprocess;
  the boundary was crossed before this existed. What ships crosses it more
  narrowly — not an arbitrary command string, but the hooks the tree already
  declares in `.pre-commit-config.yaml`, run with the tree's own config file.
- *`--repair-manifest` and the offline fallback would have to agree about "the
  base render".* **Dissolves under the scope**, once the scope is stated: this
  touches **merge inputs only**, never a hash. `cross_check` and the `--no-base`
  classification both compare `sha256` of the raw render, so neither can
  disagree with a normalised merge, because neither sees one. A normalised
  render is not a normalised record.

It is opt-in, and it advertises itself, which is the part that makes an opt-in
worth having: a plain run that conflicts re-tries those files normalised and
says so when it would have worked. The cost is one formatter pass over the set
that already went wrong, and the population that needs the flag is exactly the
population that has never read the help text.

What is deliberately **not** here is a curated subset of rules. mind.head first
attributed their 20 mechanical divergences to PEP-585 (`UP`), then re-measured
per rule family and found **zero** files reproduced by `UP` alone — import
ordering was the largest contributor, and their actual conflict was `I`. A
normalisation scoped to a "safe" typing subset would have dissolved none of
them. The general form of that mistake is worth more than the number:

> **A description attached to a verified number inherits its credibility without
> inheriting its verification.** Nobody re-derives the label sitting next to a
> figure they checked.

The sharper form arrived the same day, from the same session, in a report they
sent *after* stating that rule — which is the part worth keeping, because it
says the rule is not self-applying. Reporting the currency defect, they named
`dropped` as the term carrying their four files. It was `declined`. Their
experiment was sound and it varied exactly one thing: a tree with four deletions
against a tree with none, and the verdict flipping between them. That proves
**a standing decline suppresses the verdict**. It cannot say which of seven
names in the tuple held those files, because no tree in the experiment had
`dropped` non-empty and `declined` empty.

> **An experiment's design bounds what it can attribute.** Varying one thing
> establishes the effect and says nothing about the mechanism, so a mechanism
> read out of the source beside it is a separate claim — and it arrives wearing
> the experiment's confidence.

The fix depended on the distinction they had collapsed. `declined` has an
actionable half — the template can move past a decline, and there is then
something new to say no to — and `dropped` has none, because nothing records
that you were told, so it can never become news again. So the term is `fresh`
rather than "remove both", and the asymmetry stays visible everywhere else.

`Normaliser` never touches the user's file. Reformatting the one thing in a
three-way merge that nobody else authored would be this tool editing a file it
was not asked to edit, and it would destroy the very divergence it is trying to
read. A missing formatter is skipped on **both** sides, symmetrically, and named
in the output — silence about a tool is not coverage by it — and `--normalise`
under `--no-base` says outright that it did nothing, because a run that
normalises nothing looks exactly like a run whose normalisation found nothing.

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

### The scaffolder shipped a floor and the tool told you to fill it in

A coverage ratchet ships at `baseline_pct: 0.00%` because Invariant 6 says a
ratchet is never red on arrival. At that value it cannot fail — which is the
strongest thing that can be said for it, and it made the artifact look inert.

It is not inert, because the tool prints an instruction. A fresh tree is
**always** above its own floor, so the very first coverage run of every scaffold
ended:

```
✅ unit: 69.69% — above baseline 0.00%.
   Lock it in: python scripts/check_coverage_budget.py --suite unit --update
```

69.69% is the template's coverage of the template. There is no product code in
that tree yet; every measured statement is machinery the reader was handed, at
whatever rate its own tests happen to reach. Recording it makes the first
lightly-tested module of their own read as a regression they caused. Measured on
an `agentic` scaffold: `--update` locked in 69.69%, five modules with one test
each took the tree to 63.72%, and the nightly ratchet went red with nothing
regressed and their own coverage up from zero.

**The invariant was enforced at scaffold time and contradicted at run time by
the same repository.** That is the shape worth keeping — not "the ratchet is
premature", which is what the queued item said and is false.

#### Why the queued fix was the wrong fix

This sat as `--suites`/`--stage`: a scaffold-time flag that would omit the
ratchet, the empty suites and the health probes for a tree with no source yet.
Measuring the three killed it.

The empty suites are already tolerated by `ships_tests=False` and report as
empty rather than failing; `check health` already says `nothing to probe yet`.
Both are honest at day zero, and node-zero's measurement is the reason the third
would not have helped either: **all 136 tests in a fresh tree are the
template's, so `--suites none` cannot mean "drop the tests"** — there is nothing
of the adopter's to drop.

And for the ratchet the flag is aimed at the wrong moment entirely:

> **A flag would remove the artifact at the only moment it is harmless and leave
> it in place at the moment it does damage.** The floor cannot fail. The damage
> is an *act* — `--update` — and an act happens whenever the reader gets round
> to it, which a scaffold-time flag cannot reach.

The general form, and the reason this is filed rather than merely fixed: when a
queued item names a *flag*, check whether the hazard is a state or an event.
A flag can only condition a state.

#### A percentage is a claim about a population

The fix is that `--update` refuses while the measured population contains none
of the subject, and the invitation is not printed there. `.skeletor.json` names
every path the scaffolder wrote, so a measured file absent from it is the
project's own — and on the day a tree is scaffolded that set is exactly empty.
This is the positive form of a rule already in this repository: a negative
assertion over a possibly-empty set is a tautology, and a percentage measured
over a population that contains none of its subject is not a measurement of it.

Three things it is careful about:

- **The suppression covers the two paths that WRITE the number down, and
  nothing else.** A drop below an existing baseline is still reported: `cli/`
  and `scripts/` are the tree's code from its first commit, and a regression in
  them is real whatever the rest of the population looks like. Suppressing the
  comparison as well would have been the same mistake facing the other way.
- **No manifest is not the same answer as none of it is yours.** A tree can be
  adopted by hand or delete the file, and refusing there would make an optional
  file load-bearing for an unrelated command. It is a third value, `None`, and
  the envelope reports it as `null` rather than as a zero.
- **The refusal is only the degenerate case, and what it leaves open is not an
  edge.** Both paths that record or recommend the number state the composition
  — `287 of 2222 measured statements are your own` — with the fact printed
  before the instruction, and the reader decides. A threshold would have been a
  number nobody can defend.

I put that down as a named edge, reachable but unusual. stash.flow reached it
from a tree I had just told them was safe from it: an adopted, populated
repository, 2222 statements measured, **1935 the scaffold's and 287 their own**,
with the floor still at `0.00%` and the tool offering 76.42%.

I had predicted the opposite to them, in as many words: *"stash.flow adopted
into a populated repo, so your measured population has your own source in it
from the start and the refusal will never fire."* The conclusion was right and
the reason was wrong, which is the worse combination, because a right conclusion
stops anybody checking. Theirs:

> **Adoption into a populated repository does not imply a populated measured
> set.** What determines the measured population is the coverage configuration,
> not the repository's history.

The template ships no `[tool.coverage]` section, so bare `--cov` measures what
the run *imports*, and what the scaffold's own tests import is the scaffold's
own scripts. Product source that is not yet under test contributes nothing to
the denominator however old the repository is. The property I was reasoning
about was *does this repo have code*; the property that governs is *does the
measured set contain the adopter's code*, and a populated repo does not
automatically satisfy the second.

**The claim stops there, and stash.flow stopped it.** I wrote that they had
measured the shell-dominated case as *the normal* one, and their own throttle
came back at me: their tree is mid-rebuild, with four directories named in
`known_first_party` that are not on disk, so it is what a **paused** adopted
tree looks like. One measurement of one paused tree establishes nothing about
the distribution. A verified number with an unverified description attached to
it — the failure this document names two sections earlier, walked into while
writing up somebody else's correction.

What survives is enough, and it is the better argument anyway. I had been
justifying the composition line as *most adopted trees are shell-heavy, so show
the number*, which nobody has measured. The version that does not need the
distribution: **no cheap predicate tells an adopter whether their measured set
is shell-dominated**, the obvious one is the one stash.flow falsified, and it
fails in the reassuring direction. With the predicate a reader would reach for
wrong and no second one available, the number has to be shown rather than
inferred. The refusal is the one point on that range where no judgement is
possible.

#### The half no tree can ask about itself

The tree ships `tests/test_coverage_population.py`, which feeds the checker a
synthetic report and a synthetic manifest. It proves the classification is right
about the data it is handed, and it would pass unchanged on a generator whose
manifest omitted half the files it wrote — because that omission is in the data,
not in the code.

So `bin/skeletor-verify` runs the live question: a real coverage pass over a
real fresh tree, and `--update` must refuse. Established by planting a
`skeletor-new` that drops one file from the manifest — the gate goes red, and
**the tree's own six tests stay green**, which is the two-homes split measured
rather than asserted. Both directions run in the same tree: one module and one
test of its own, and the baseline it just refused is recorded.

A module alone does not do it, which is worth knowing before writing that
fixture: bare `--cov` measures what is imported, so an untested file is
invisible to coverage and the population does not move. What lifts a tree out of
the degenerate case is the first *test* of its own — the act the refusal is
waiting for anyway.

### Two tiers where the debug loop was permanently red

Found by the change above, on `bin/skeletor-verify --tier core`. Four gates run
against `fullest = max(selected tiers)`, which is `agentic` for the grid and
`core` when somebody narrows — and `versioning_gate` asserted that the default
mode ships all four paths `--versioning tag` subtracts. One of them,
`.claude/skills/release/SKILL.md`, is `agentic`'s. So the documented debug loop
had a standing red on a check that is correct at the tier CI runs.

`--tier` is for narrowing a debug loop, and a debug loop with a permanent red in
it teaches a reader that red is normal — this repository's own objection to a
gate that is red on arrival, arriving in the tool that enforces it.

The fix is to scope the assertion to what *this tier's* default actually ships,
measured rather than assumed. What makes it worth writing down is the second
pass: narrowing it silently dropped the check it used to carry. "The default
must ship every entry" had been catching a `VERSIONING` entry that no overlay
ships at all, and after the fix such an entry read as "out of scope at this
tier" and passed. **A term set corrected in one direction and overshot** — the
class four defects landed in the day before, arriving inside the correction for
a fifth. Both questions are asserted now, from different sources: the tier's
default for scope, and `template/` directly for staleness.

The staleness half then shipped broken and its own plant said so.
`any(template.glob(depth + rel) for depth in ...)` is true for every path,
because a glob generator is truthy before it yields anything — so the outer
`any` was testing the depth list and never the tree. Green for every entry,
including one no overlay ships. It is the same mistake as `elem or default` on
an `ElementTree` node, made twice in one afternoon in two files, which is the
argument for planting rather than reading: both were obviously correct on the
page.

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

## Capture lanes: a queue you can file into is a queue you can see

The template shipped `{{CLI}} bug` from early on. It filed a GitHub issue under
`agent-bug` and **nothing in any generated tree ever read that label back.**
Filing worked, every time, and the queue was invisible.

That is a specific and recurring shape rather than an oversight: *the write side
of a mechanism is the half somebody notices is missing.* A capture that fails is
loud. A capture that succeeds into a queue nobody looks at is indistinguishable,
from the caller's side, from one that was acted on.

Three things came out of closing it, and only the first is the feature.

**A registry, because two intakes written separately are two invisible queues.**
`scripts/lanes.py` owns the label, its colour, its required body sections and
the job key that would drain it. `{{SHELL_PACKAGE}}/_capture.py` is one engine
wearing whichever lane it is handed, and `bug.py` and `task.py` are prose and a
binding. The design is jam.sense's, arrived at after they wrote their second
intake, and their reason is the one that generalises: *this module's whole job
is to stop a finding being lost, and a second, subtly-different copy of it is
how the next intake loses one.*

**The `--label` override was removed, and its removal is the point.** It
defaulted to the lane label and accepted anything, which made it a way to file
into a queue that does not exist — nothing lists it, nothing drains it, no view
shows it. The queue *is* the label.

**The drain note is derived, never stored.** A lane names the job key that would
empty it; `drain_note()` asks the job registry and reports what it finds. jam.sense
measured the alternative: their stored copy of a drain time read 07:00 for two
weeks after that fire was retired, sitting one import away from the registry
field that said 07:45 — and it was printed on a path nobody re-reads, a capture
that succeeded, so the drift stayed invisible until somebody planned around it.

### The view is generated, and the generator is the part that could be wrong

`.vscode/settings.json`'s `githubIssues.queries` and
`githubPullRequests.queries` are rendered from the registry into a marked
region. Three details each cost something:

- **The complement query is a negation over the registry.** Without one, an
  issue opened in the browser under no lane label sits in no pane at all. Written
  by hand it is wrong the moment a lane is added; derived, it is a true
  complement for free.
- **Text splicing, not a JSON round-trip.** A round-trip preserves every key and
  silently drops every comment in a JSONC file. The file still parses and still
  works afterwards, and the reasons somebody wrote down are gone.
- **The generator creates the file; the overlay does not ship one.** It shipped
  as a plain template file for about an hour, which meant a `--force` scaffold —
  the case `AGENTS.md` calls *the usual case* — replaced whatever editor settings
  the repository already had. Measured on a tree carrying `editor.formatOnSave`
  and a strict type-checking mode: both gone, nothing said. Nearly every other
  file here is machinery, where a collision is the adoption working; this one is
  the reader's own configuration and skeletor has a claim on two keys of it.
- **The drafts pane's *name* is derived from the job registry.** "Overnight
  Drafts" is only true in a tree with something committing unattended. jam.sense
  can hardcode it; a template cannot, because the same string is a small lie at
  `core`. Planting the hardcoded form turns two of five configurations red and
  leaves the rest green — which is the whole argument for deriving it, executed.

### Same artifact, two questions, two homes

The split this repository keeps arriving at, at one more artifact:

* **the tree** asks whether its views have drifted from its registry since it
  was scaffolded — `tests/test_lanes.py`, which the generator cannot ask because
  the generator is gone by then;
* **the generator** asks whether the region it handed over is right for *that
  tier*, and whether the post-copy step that writes it ran at all —
  `lane_views_gate`, which no tree can ask because a tree only ever holds one
  configuration.

The second half is not hypothetical. `post_copy_steps` fires the generator with
`capture_output=True` and no return check, the same shape as `regen.py` beside
it, so a failure there ships markers with nothing between them. Planting exactly
that turns all five gated configurations red with the sentence *"the region
between the markers is empty — the post-copy generator did not run."*

### What did not ship, and why the boundary is there

The lanes are the **capture** side. jam.sense's drainers are 2500 lines of
monitors, escalation policy and run-ledger machinery, and they did not come
across — `jobs.py` ships exactly one fully-worked entry on purpose, because a
registry seeded with keys whose modules do not exist is a registry whose own
tests are red on arrival. A tree with no drainer says so, in those words, in
every pane and after every successful capture. Add a job with the lane's
`drainer_job` key and every consumer picks up its schedule with no second edit;
that path is exercised by planting the job and reading the rendered label back.

The same reasoning excluded a test-gap lane: it has no producer here, and **a
view whose label nothing can create is empty forever, which is exactly what a
drained queue looks like.**

## Upstream is a direction, and it had been recorded backwards

skeletor was extracted from one mature production repository. That repository
kept going, so there are two questions with the same words:

* *are the trees I generate current with me?* — `.skeletor.json`,
  `bin/skeletor-upgrade`, and the workspace's currency ledger;
* *am I current with the repository I came from?* — which nothing asked.

For a while the second was recorded as though it were the first. The source
repository carried a `.skeletor-components.json` naming six files it had copied
back out of the template, so the ledger listed it as an adopter, measured it as
37 releases behind, and reported four deliberate forks as staleness. It was
answered with a hold — an exemption saying *this one is not expected to move* —
which was true and was quieting a question that should never have been asked.

**A component manifest describes a downstream relationship. Pointing one at the
repository you were extracted from inverts the arrow, and every reading after
that is wrong in the reassuring direction:** it produces a row that says
somebody owes work, in a tree where nobody does.

Deleted, and replaced with `upstream.json` — the same provenance in the
direction it actually runs. It records what was taken, from where, why, and the
commit the source has been read through. `bin/skeletor-maintain` reads it as a
third cheap question beside CI and pins, and, like `bin/skeletor-check-pins`, it
**reports and never adopts**: which of an upstream's changes generalises is a
judgment, and the machine's job is to say where to look and how far you have
already read.

Two things it learned the hard way. It locates the checkout **by origin URL**,
never by a recorded path, because a path is right on one machine and wrong on
every other — and a stale one resolves to *some* directory and reads that
history instead of failing. And it **skips linked worktrees**, because every
worktree of a repository reports the same origin: the first run matched a
dependency-bump worktree that sorted first alphabetically and reported 11
commits of a Dependabot branch as upstream movement.

The file also carries a `_not_taken` section, which is the half that pays.
Without it the next pass re-reads the same module and reaches the same
conclusion, and **a decision that has to be re-made on a schedule is not a
decision** — the same argument that stopped `bin/skeletor-upgrade` restoring
files a user had deleted.

## A release no adopter can observe

`bin/skeletor-upgrade` records the ref it **rendered from**, so a release that
changes `bin/` and no template file produces nothing an adopter can see. Their
upgrade reports `already current`, `.skeletor.json` is correctly never
rewritten, and the currency ledger keeps showing the older ref — on a tree that
is byte-identical to the newer template and has run the newer binary.

sky.boss reported the shape at v0.20.1 and their framing is the useful one:

> This is not *the ledger is behind*. It is **the ledger has no expressible
> answer.**

It is a different animal from a stale copy. There is no second home to delete
and no command to run instead, because the fact — *which version of the tool
produced this state* — is not a property of the tree at all. The ref records a
render, and a release that renders nothing new has no render to name.

`dd27dc4` is the worked instance and it arrived four minutes after `v0.26.0` was
tagged. `pinned_ref_gate`'s fixture cut a branch at the newest tag and took
`bin/skeletor-upgrade` from the tip to get the tool under test — a no-op when
the tip **is** the tag, which is exactly the release commit. Nothing staged, no
commit, the branch stayed on the tag, `git describe` returned the bare tag, and
the fixture's own guard correctly reported it was no longer the trap. Green
through every development run, red on the one run nobody skips.

Two things follow, and only the first is a rule about this file's subject.

**A fixture whose shape depends on where HEAD sits relative to the newest tag
has a release-shaped hole.** The remedy is to make the fixture unconditional —
here, a marker file outside `template/`, so the extra commit always exists and
the render stays the tag's byte for byte. And the grid is worth running once
*after* tagging and before pushing the tag: local green before the tag does not
cover the state being released.

**The fix was correctly not tagged.** It touches `bin/` and no template file, so
there is nothing to scaffold against, and tagging it would manufacture exactly
the unobservable release described above. `v0.26.0` stands — its template was
never affected — and a pushed ref is not moved to tidy a red run out of its
history.

## Drift has a copy to delete. This has nothing to point at

This repository's governing rule about stale facts presupposes a copy: *do not
keep a copy of what a command will tell you.* The worktree list, the four-of-five
count, the `5 of 5` row — every one of them had an instrument available and used
a second home instead, and the remedy is always the same: delete the copy, run
the command.

**A release produced a false sentence with no copy behind it, and that is a
different animal.** `bin/skeletor-upgrade` prints, on the most reassuring line
it has:

> being behind by a ref and being behind by a file are different, and only the
> second is work

True when written. Nothing was copied, nothing went stale, and the sentence
still describes the mechanism it was written about — the manifest really is
re-copied only by a run that applies something. Then `--ref` shipped two
releases later, in a different file, and recording a ref the operator *chose*
became work the tool can do. **What changed is the set the sentence quantifies
over.**

No gate can see that, and the reason is worth being exact about: **neither
artifact is wrong.** The sentence is a correct description of the manifest rule.
`--ref` is correct on its own terms. A checker comparing either against its
subject finds nothing, because the defect is in the relationship between two
things that never had to agree before one of them existed.

So the class is:

> **Drift is a copy that stopped matching its source. This is a claim whose
> scope was narrowed by something else, and scope is not stored anywhere.**

The remedies differ, which is why filing the two together would be a mistake.
Drift is fixed structurally — delete the copy, derive the value. This one has
nothing to delete and nothing to derive, so the only defence is the habit: **when
you add a capability, re-read the sentences that describe what the tool cannot
do.** A feature's blast radius includes every place the old limitation was
offered as reassurance, and those places are the hardest to find precisely
because they are not about the feature.

The workspace declined to file this as drift and was right to. Two instances in
one release, both found by running the tool rather than reading it:

* the `--ref` gap itself — `--ref` could not correct an already-current tree,
  because two correct rules composed into one. The flag records on any run that
  applies something; the manifest is re-copied only by such a run; a tree that
  is already current applies nothing. That is precisely the population the flag
  was built for, and `--ported` does not reach it either, being a re-run.
* five documents claiming `ready_for_review` "runs the full set before it can
  merge", which the classifier's own verdict table denied on the line above.

The second one has a companion lesson about instruments rather than sentences.
That table had the two rows adjacent and identical for several releases, and the
gate beside it asserted only that the transition never *loses* a job — so the
measurement existed and the question did not. **A table that answers a question
is not the same as anybody having asked it.** Both directions are asserted now.

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

### The completeness claim that stopped four people looking

`check pre-push` opened with *"Everything CI blocks on, in the order that fails
fastest."* It was not. It omitted `check_skip_budget.py` and
`check_commit_subjects.py` — both blocking, both perfectly runnable on a host —
and the integration suite, which is blocking and genuinely is not.

proto.pilot paid for it the expensive way: `pre-push` green, push, CI red on the
skip budget, four times across four upgrades. The missing gate is not the
interesting part. **The sentence was doing active work to stop them looking** —
a gate that is absent announces itself the first time something slips through,
and a gate that is absent *behind a completeness claim* converts every red CI
run into a puzzle about CI. This repository ranks that failure worst, and had
committed it in the docstring of the command it tells every new user to run
first.

`tests/test_pre_push_covers_ci.py` is the answer, and it is a **partition**
rather than the obvious assertion. Every blocking check is either reachable from
`pre_push` or declared in `UNREACHABLE` with a reason; **a check in neither is
the failure.** The obvious version — every blocking gate is reachable — is red
on a fresh scaffold, because the integration job needs a stack this host does not
have. proto.pilot proposed that version and withdrew it on exactly that ground.
The partition is `cli/test_cmds.py`'s `scheduled` / `UNSCHEDULED` shape reused:
an exemption has to say which kind it is, and both staleness directions are
asserted, so an entry outlives its reason loudly.

**The gate found two bugs in itself on its first run, and both are the same
bug.** `-m` is two flags: `python -m pytest` names a module and `pytest -m unit`
names a marker, so a pattern that took whatever followed `-m` reported a blocking
suite called `pytest` — a check that does not exist, invented by the gate whose
entire job is noticing checks that are missing. And scanning `ci.yml` whole
reported the `ui` suite, which no job `needs:` and which therefore holds no push
up. Both are *true statements about `ci.yml` and wrong answers to the question
asked*, which is this repository's most-repeated failure arriving inside the
instrument built to catch a version of it.

The `ui` one is worth more than its fix. Left in, the gate would have demanded
`pre-push` run a suite `ci.yml` deliberately keeps out of `needs:` — and `ci.yml`
says why, at the `release-please` job: `ui` is the one job a repo with nothing
marked `ui` deletes, and a `needs:` naming a deleted job is a `startup_failure`
rather than a red job. So **the correction for a claim that was too weak was, on
the first run, a claim that was too strong**, in the same file, about the same
command. The remedy is not a filter on the output: markers are read from
`pytest.ini` and blocking is derived from `needs:`, which makes both wrong
answers unrepresentable rather than excluded.

Four plants, each asserting it landed before writing: drop a script from
`pre_push`, add `ui` to `needs:`, drop `integration` from `needs:`, and point
`pre_push`'s pytest call at the integration marker. Each goes red on exactly one
of the four tests. The second is the load-bearing one — without it, `ui` passing
is indistinguishable from `ui` being skipped for the wrong reason.

**The sentence had five homes and fixing the docstring left four.** The README
said "everything CI blocks on", `AGENTS.md` said "everything CI blocks on",
`docs/rules/testing.md` said "everything CI runs, locally", and
`docs/DEVELOPMENT.md` opened a section with the strongest form of all —
*"Everything CI blocks on is runnable locally, with the same invocation"* — as a
property of the repository rather than a note on a command. The docstring is the
copy the author is looking at while fixing the command; the other four are the
copies a reader consults. A test that holds the *behaviour* to the truth does
nothing at all for four prose copies of the false claim, which is the limit
worth stating: **a gate proves the thing, and every unlinked restatement of the
thing is still unproven.**

A prose gate was considered and declined, with the reason recorded here rather
than left as silence. A sound derived predicate exists — the tree knows
`UNREACHABLE`, so while it is non-empty any doc asserting `pre-push == CI` is
false — but the only enrolment available is "a line naming `check pre-push`",
and the only requirement expressible is "the surrounding block names the
exception". That would force a one-line quickstart comment to carry the
integration caveat in four documents whose job is to be short. The alternative,
a word list of superlatives, is the registry Rule 2 exists to refuse. So the
five sentences are simply true now, and this paragraph is the record that the
drift is unguarded.


### The one fact a green tree cannot state about itself

Every mechanism in this document is a tree checking itself. Release Please is
the place that stops working, and the reason is not in any file a scaffold
ships.

The action opens a pull request. `can_approve_pull_request_reviews` is a
repo- or organisation-level switch deciding whether Actions may, and **no
`permissions:` block in any workflow can lift it.** mind.head's job carried
`contents: write, pull-requests: write`, and the run got all the way through —
branch created, tree written, commit made, ref updated — then failed on the PR
call alone with *"GitHub Actions is not permitted to create or approve pull
requests."* Everything before that line succeeded, which is why it reads as a
release that nearly worked rather than as a permission that was never granted.

**That is the class this repository has no instrument for, and it is the inverse
of everything else here.** A gate can ask whether a tree agrees with itself. It
cannot ask about the account the tree runs under. So a scaffold can be entirely
green, ship 186 passing checks, and hand over a release pipeline whose first real
use fails — and the only instrument that sees it is somebody trying to release.
stash.flow states the sibling case from the other axis: *a mechanism gated on a
branch you do not work on cannot be evaluated by using the repository.* Both are
the repository being the wrong unit of observation — one because the fact lives
in the account, one because it lives in an event the tree never triggers. The
test for the class: **would this be visible to a tree that was entirely green?**

The remedy is a setup step, in `docs/SETUP_GUIDE.md` beside branch protection,
because that is the only place a fact outside every file can live.

**What the template can contribute is a seam, not a fix**, and the distinction is
load-bearing. The release job now takes
`token: ${{ secrets.RELEASE_TOKEN || github.token }}`. The switch binds
`GITHUB_TOKEN`, the Actions identity; a PAT is a *user* identity, so it is not
what is being refused, and that input is how a PAT reaches the action with no
workflow edit at all.

**It cannot carry a GitHub App, and the first version of this section said it
could.** That is the more instructive half. A secret holds a static string; an
App issues an app id and a private key which a *step* exchanges for a one-hour
installation token at run time — `actions/create-github-app-token`, which is
precisely what jam.sense runs and precisely what this section had just finished
declining to ship. So the paragraph recommended, as the remedy for an adopter
with an App, a mechanism that structurally cannot serve one. **The seam's stated
purpose and its capability came apart in the same commit that introduced it**,
and the sentence read fluently because both halves were separately true: the
switch really does not bind an App, and an unset secret really does fall
through.

Two things made it survivable to write. The measurement I had just run was real
and answered a *different* question — whether `||` falls through — so the
paragraph carried the authority of a verified claim next to an unverified one,
which is the conjunction failure this document already records under template
prose. And the org has exactly one App, on one repository, so there was no
adopter to try the advice and no gate anywhere that reads English. skyrow-
workspace found it by reading the App registration, an hour after the tag.

The corrected shape is three doors, in `docs/SETUP_GUIDE.md`: the switch — which
**an enterprise policy can close outright**, stash.flow having taken a `409`
reading *"The enterprise does not allow GitHub Actions to create or approve pull
requests"* — then a PAT in `RELEASE_TOKEN`, then an App, whose exact workflow
edit is written out both there and in `ci.yml` itself rather than pointed at.

**The pointing is its own correction.** The first fix cited
`docs/SETUP_GUIDE.md` from a comment inside `template/core/`, and no tier ships
that file: Invariant 7 broken in the act of repairing a different sentence. The
tier-composition gate cannot catch it either — its predicate is *absent here and
present in a configuration that ships strictly more*, and skeletor's own docs are
absent from every configuration, so they fall through the same hole that
deliberately exempts URLs and other repositories' paths. A path that exists in
this checkout and in no scaffold looks resolvable to the only person who can see
it. Measured across `template/` afterwards: exactly one instance, now zero.

The app-token **step** still does not ship, but the reason first given was
weaker than it sounded. "Two secrets a scaffold cannot populate, so red on
arrival" is avoidable — a job-level `env:` bridging the secret into a step-level
`if:` skips it cleanly, the bridge being necessary because the `secrets` context
is not readable from a step's `if:`. What survives is that nobody has measured
that guarded form on a runner, and that `--versioning` is *a subtraction and
nothing else* by design, because a mode that wrote files differently needs a
verification grid this repository cannot afford. **Those are reasons to wait,
not reasons it is impossible**, and the difference is what the first version
obscured.

**The line was measured, not reasoned, and the reason is the sharpest part.**
`actionlint` runs in `bin/skeletor-verify` and holds the expression's syntax — and
it knows nothing about which secrets exist in the account a tree runs under,
which is `can_approve_pull_request_reviews` one field over. Saying "actionlint
covers it" would have been the completeness claim two sections up, written the
same evening, about a different file. mind.head caught it after proposing the
line, having found **zero** instances of the idiom anywhere in this workspace to
reason from: jam.sense passes its App token unconditionally, because it has real
secrets. So a throwaway branch, one dispatched run, three booleans off a real
runner:

```
unset-is-empty:      true      # secrets.RELEASE_TOKEN == ''
or-yields-fallback:  true      # (secrets.RELEASE_TOKEN || 'FALLBACK') == 'FALLBACK'
or-yields-gh-token:  true      # (secrets.RELEASE_TOKEN || github.token) == github.token
```

The failure mode that justified the five minutes is mind.head's, and it is
unpleasantly well aimed: the fallthrough executes **only** in a tree that has a
release config — one actually cutting releases — and if it misbehaved it would
hand the action an empty token, presenting as an auth error that every reader in
this organisation would now misattribute to the switch. **A wrong answer wearing
the costume of the thing you have just finished diagnosing is worse than a wrong
answer.**



### A green that means "clean" and a green that means "could not check"

`skeletor-components` classifies a taken file by two independent comparisons and
then says what the record can support about the *baseline* — the moment the file
was taken. That baseline has three states and it shipped with two sentences.

`source_sha == local_sha` at record time is a file that **provably** matched the
template. A file with placeholders that differed is one nothing can rule on,
because rendering and editing produce the same signal. Both printed
*"unchanged on both sides since you recorded it"*. So `scripts/allowlist.py`,
genuinely pristine, and `tests/test_pyright_scope.py`, a real fork — `jam check
docs` become `jam check markdown`, a `# noqa: E402` dropped — rendered the
identical line, under the identical `✅`.

**This is the null-result rule landing on the instrument built to hold it.** The
tool's own docstring already said the record cannot tell a fork from a rendering;
what it did not say is that *not guessing* and *not saying* are different acts.
Declining to rule is correct. Rendering the declined case as the clean case is a
claim, and a false one.

jam.sense's sharpening is why it ranks high rather than as a wording nit:
**nobody investigates a `✅`.** The cost of a collapsed state is highest exactly
where the state is silent — an `⬆️` line at least sends a reader to a diff, and
the green line is the one a person skimming for drift never stops at. That is
the same argument this document makes about `check pre-push`'s docstring one
section up, arriving at a different artifact within the day: a claim of coverage
is worse than a gap, because it is doing active work to stop somebody looking.

The fix names the third state — `baseline` is `matched`, `forked` or `unknown`
on every JSON row, so a consumer is not left recovering it by parsing English —
and appends the clause to all four states rather than folding it into one, which
puts the three spellings adjacent in the output where a reader comparing two
lines can see they differ.

**The gate that missed it is the more useful lesson.** `components_gate` already
asserted the fork sentence, with `qualified = "since you recorded it"` — a
substring of *every* spelling, so the assertion passed under all three and could
not have failed. And its fixture could not have discriminated either: the
`consumer` tree copies template files verbatim, so every baseline there is
`matched`, and only the deliberately-forked tree produces the other two. **One
fixture cannot hold three states, and the one anybody reaches for first holds
the state that is already correct.** The assertion now spans both trees and
compares the machine field, and the plant that establishes it is the shipped bug
itself: collapsing `unknown` back into `matched` turns it red.


### Committing the work silenced the warning without changing the risk

`skeletor-upgrade` renders `ours` from the **live checkout**, not from a ref —
there is no `--ref`, and `--from-dir` overrides the *base*. So whatever is at
skeletor's HEAD is what an adopter gets, and the only question the report ever
asked about that checkout was *is it dirty*.

stash.flow was blocked twice by the same content and the second time the report
had gone quiet. The runs are the finding:

```
DIRTY (before the commit)         CLEAN (after it)
⚠️  6 uncommitted change(s)        → base: skeletor @ v0.12.0
✅ 6 updated  · cli/check.py       ✅ 6 updated  · cli/check.py
                                   (no caveat of any kind)
```

**The plans were identical, row for row** — the same 52 lines of `cli/check.py`
in both. What changed is that committing satisfied the only predicate anybody
was checking, while nothing about whether a third party could reach that content
had changed at all. The report was at its most reassuring in the state where an
adopter could verify least.

There is a ladder here and `render_dirt` answers one rung of it:

| state | resolvable by others | before this |
| --- | --- | --- |
| uncommitted | never | refused, loudly |
| unpushed | this machine only | silent |
| pushed, untagged | anywhere | silent |
| tagged | anywhere | silent, correctly |

**Rung two is the tool's problem and rung three is the adopter's**, and the line
between them is worth stating because it decides what the fix is allowed to do.
An adopter who wants HEAD is entitled to HEAD, so *untagged* is a policy this
tool must not hold an opinion about — stash.flow's loop takes tags and declines;
somebody else's does not. But **no policy makes a one-machine ref acceptable.**
`base_checkout()` resolves a recorded ref with `git worktree add`, so a manifest
stamped `v0.14.0-2-g8d9bddb` while those two commits are unpushed is
reproducible on exactly one computer.

Which is this repository's own `-dirty` defect with the clock run forward, and
the sentence needs one word changed: a dirty base *names a render nobody can
resolve*; an unpushed base names one nobody can resolve **yet** — and *yet* does
no work whatever against an amend, a rebase, or a branch that is dropped. The
guard reads `git status --porcelain`, which went quiet the instant the work was
committed, while the durability question it exists to protect was untouched.
**A ref that resolves is not a ref that means anything to the reader, and the
gate only ever checked the first.**

`head_standing()` reports the other rungs, and the split is between a *fact* and
a *judgement* rather than between two paths. Every run — dry or not — opens with
the position and **both** counts:

```
→ head: skeletor @ v0.14.0-2-g8d9bddb (2 past the last release tag, 2 not on origin/main)
```

The `⚠️` is on the writing path alone. That line took a correction from
stash.flow after they had already taken the first version: it reported distance
from the tag and stayed silent on the push state, so the fact with an acceptable
policy behind it was shown and the fact with none was not — **the argument for
keeping the mark off the dry run is an argument about the mark, not about the
fact**, and the dry run is the path a peer session reads while the writing path
is read by somebody who has already decided.
Warning on every dry run would fire through this repository's own grid, where an
unpushed HEAD is the ordinary state between a commit and a push — **a true
warning that fires constantly is one nobody reads**, which is the failure mode
this whole document is about, arriving as the fix rather than as the bug.

Verified in all four states rather than in the one that motivated it: unpushed
warns with a count, **pushed goes silent**, no upstream warns differently
(`None` is not zero — nothing is reachable, so there is no count to give), and a
dry run states the position without the mark. The pushed case is the one that
matters, because a warning that never clears is indistinguishable from a warning
that is not looking.

---

### A gate that ran on every laptop and in no CI anywhere

`tests/test_pre_push_covers_ci.py` compares two sets and subtracts them in one
direction:

```python
orphans = sorted(set(blocking) - reached - set(UNREACHABLE))
```

`blocking` is what `ci.yml` gates on, `reached` is what `pre_push` runs. Its
three sibling tests all police `UNREACHABLE` itself. Every one of them takes
`ci.yml` as the authority and asks whether `pre-push` keeps up — which is the
right premise for every check the template shipped, and inverts for the one it
did not.

**No shipped workflow installed node.** Zero occurrences of
`npm|setup-node|vitest|eslint|yarn|pnpm` across `ci.yml`,
`docs-validation.yml`, `pr-draft-discipline.yml` and `coverage-nightly.yml`, and
`template/node/` ships no workflow of its own. Meanwhile `cli/check.py::_lint()`
runs `npm run lint:check` whenever `eslint.config.js` exists, and `pre_push`
calls `_lint()`. So eslint was a gate that ran on every developer's machine and
in no CI anywhere, and **`nothing computes `_pre_push_reaches() - blocking``**,
so the set difference that would have found it is the one nobody wrote.

The reason it survived here is a variant rather than a repeat of
`gated_language`. `bin/skeletor-verify` **does** run `npm run lint:check` and
`npm run format:check`, on the `agentic/both` tree. The node lints were covered
— in the generator's grid. **A gate that runs upstream can mask its own absence
downstream**, and from inside this repository that coverage looked general.
dream-doll found it by being the fleet's only `--language node` adopter and
watching six green jobs run none of their product's checks.

The steps go in the existing `lint` job rather than a new one, and that is a
constraint rather than a preference: `lint` is already in `release-please`'s
`needs:`, so a new job would put a fifth name in that list, and a `needs:`
naming a job a tree deletes is the `startup_failure` this document already
records against the `ui` marker. They guard the way the release job guards its
config — a `run:` step setting an output from `[ -f package.json ]`, an
`::notice` when absent, and `if:` on the four that follow — so the job still
runs and still reports whatever a tree ships.

Two narrowings, because the first report overstated in the direction that makes
a fix look more urgent. The template's `package.json` ships `lint:check`,
`lint:fix`, `format:check` and `format` and no `test`, `build` or `typecheck`,
so *"CI never tests the product"* is true of an adopter who added those and
overstated for a fresh scaffold, where there is nothing yet to test. And the
`ui` and `integration` jobs collecting zero tests and passing is the empty-suite
tolerance working, not a symptom of this.

`lts/*` rather than a pinned node, deliberately: this template ships no lockfile
and no `engines` field, so there is no version here to be faithful **to**, and a
number invented in a generator is one every adopter inherits and nobody
maintains. `npm install --no-audit --no-fund` rather than `npm ci` for the same
reason — `ci` needs the lockfile — and it is the flag set `bin/skeletor-verify`
already uses, so the grid and the tree install identically.

### A detector that would have been its own first finding

`d5ab96c` removed three home-relative literals naming this checkout from
`README.md` and shipped no mechanism, which left this repository carrying a live instance of a class it had
just named in prose: `AGENTS.md` says *a path in prose is wrong for every
checkout but the one it was authored on*, and a rule whose only enforcement is a
sentence stating it is precisely the thing that sentence is about.

The gate is unremarkable. What is worth recording is the shape of the trap it
had to avoid, because it was demonstrated the same afternoon: a session ran
`pkill -f "bin/skeletor-verify"` inside a compound command whose own argv
contained that string, matched the shell running it, and killed its own grid at
the first statement — reported as `exit 144` with empty output, which reads
exactly like a failed verification rather than a self-inflicted one. **A pattern
that matches the thing doing the matching.**

A scan for `~/<checkout>` written the obvious way is that bug: the detector's
own source contains the literal, so the gate is its own first finding. The
available answers are to exempt the detector's own file — a second allowlist
entry, for a reason unrelated to the first, and the count of entries is how you
notice a predicate is wrong — or to make the collision impossible. The needle is
assembled from `SKELETOR.name` behind a home prefix, so no occurrence of the
string exists in the file that hunts it. **A gate that cannot be its own finding
by construction beats one that is careful not to be.**

Deriving it also states the better rule: the defect was never those six letters,
it is *this checkout's own location, written where a stranger will read it*.

**Its first red was this section.** The paragraph above originally spelled the
literal it describes, so the gate's opening run failed on the document
explaining the gate — which is the vocabulary problem sky.boss named from a
doc-link check: prose *about* a notation that no predicate over the notation can
see out of. The available fix was a second allowlist entry, and the bar this
repository sets is that a second entry means the predicate is wrong. The prose
was reworded instead, to *three home-relative literals naming this checkout*,
which is both exempt-free and the more accurate sentence — the finding was never
about those six characters. **An exemption would have bought a worse document.**

**Both gates asked the directory what only the remote knows, and it is fixed
rather than filed.** `SKELETOR.name` is where this repository *sits*, not what
it *is*, and the two coincide only in a canonically-named clone.
`author_tokens()` documented *"the checkout's own name is excluded"* and
implemented it as `part != SKELETOR.name`; the path gate built its needle the
same way and was therefore silently blind in a clone named anything else.

The bug that made it concrete cannot occur where anybody works. `git clone .`
records origin as `<path>/.`, and the old owner pattern read the trailing `.` as
the repository, shifting one component left:

```
https://github.com/skyrowlabs/skeletor.git   -> skyrowlabs   correct
/home/jeston/skyrow.labs/skeletor            -> skyrow.labs  correct
/home/jeston/skyrow.labs/skeletor/.          -> skeletor     wrong
```

So the repository's own name arrived through the input designed to name the
**owner**, became a forbidden token, and every rendered `.skeletor.json` read as
an author leak. The other skeletor session hit it running the grid from a
scratch clone and found it by measuring `author_tokens()`'s inputs rather than
reconstructing them — which is why the diagnosis from this side, aimed at the
path, was wrong. **The path was never the input that mattered.**

`parse_origin` is pure and `identity_gate` puts eight spellings through it. A
table beats a discovered set for once, and the reason is the reason the bug
existed: these are git's output formats, they change on git's schedule, and
**the case that matters is unreachable from any checkout anybody runs the grid
in.** A canonical clone answers correctly however the parser is written. That is
this project's founding class arriving inside its own verifier.

Three things the gate caught about its own fix, in the order it caught them:

- **The parser's only defence was a caller.** `error: No such remote 'origin'`
  parsed as owner `error`, and nothing but `repository_identity()` checking a
  return code stopped it. It declines whitespace now; both guards stay, and they
  fail independently.
- **A normalisation loop that looked load-bearing was dead.** Deleting it left
  the gate green, because the component filter already drops `.` and empty
  segments. *A plant that does not land is indistinguishable from a gate that
  works* — here it said the mechanism was somewhere else, and the loop went.
- **The plant against the filter reproduces the original defect exactly**,
  `('skeletor', '.')`, which is what makes the green mean anything.

The needle is now both names — what the repository *is* and where this clone
*sits* — because they answer different halves and are usually the same string:
prose calls a repository by its identity, and somebody transcribing their own
shell pastes the directory.

### A parser tolerant of what it cannot find was also tolerating what it could not represent

`scripts/docs/frontmatter.py` is a hand-rolled reader for a flat schema this
project also writes, and its docstring scopes it correctly: *"emitted by `dumps`
in this same module."* `add_frontmatter.py` runs it over **hand-written**
documents, so the scoping sentence was doing no work at the one call site that
mattered.

sky.boss found it folding 24 real documents into a scaffolded tree. Three
shapes, all legal YAML, **none of which failed**:

| Written | Returned | Consequence |
| --- | --- | --- |
| `agent_value: 3  # four rounds` | `'3  # four rounds'` | `gen_impl_index.py` runs `int()` inside `except (TypeError, ValueError)` that defaults to `1` — *historical only* |
| `key_files: [a, b,` ⏎ `  c]` | `'[a, b,'` | the rest of the list read as body text |
| `key_files:` ⏎ `  - a` ⏎ `  - b` | `''` | the whole list, gone |

The first is the one to rank, and not because it loses data: it **manufactures a
judgment about how much a document is worth reading.** 4 of their 24 docs
carried that comment and they were the four densest — so the archive would have
sorted the best material to the bottom of every category, labelled ⭐ historical
only, with no error anywhere.

**Where the line goes, which is narrower than "raise on malformed".** `parse()`'s
tolerance had a written reason — *a doc that fails to parse must still be listed
as unclassified rather than crashing the index build for every other doc* — and
Invariant 1 says a rule whose reason is written down can be evaluated when it
becomes inconvenient. Evaluated: that reason is about **absence**. A block
sequence does not fail to parse; it parses to a wrong value. The tolerance was
written for one thing and was silently covering another, and only the second is
unnoticeable.

So the split is by *what the parser can see*, not by severity:

- a block it cannot **find** — no frontmatter, unterminated — still returns
  `({}, text)`. Unchanged.
- a construct inside a found block that it cannot **represent** raises
  `FrontmatterError`, naming file, line and key.

A trailing comment is neither: it is stripped, because that is what YAML means
and this schema is flat enough for the rule to be unambiguous. `_emit` now quotes
any value containing `#` so the round trip holds — otherwise the fix would have
traded one silent corruption for another.

**The habit came from this template.** `docs/TODO/_TEMPLATE.md` shows
`> **Queue-Order**: 40   # only on a ready plan` on a header line, where it is
fine. Four lines above, inside the frontmatter block, it was not — and nothing
in the document says the two halves have different rules.

**And the same report carried a second finding worth more than it was offered
as.** `check_doc_tables.py` printed `N subfolder(s) routed` where `N` was every
directory under `docs/` counted off the disk, minus the stranded ones. sky.boss
raised it as phrasing and thought the number coincided with the truth whenever
the gate passed. It does not: `unrouted()` deliberately does not descend into a
routed folder, so the count included folders the check never examined. A fresh
agentic tree printed **7**; the set a table row actually reached is **4**.

It was arithmetic wearing a verdict's clothes, and the failure mode is this
document's most repeated one — it would have gone on printing "everything
routed" if the matching predicate narrowed to nothing, because the disk does not
care what the tables say. `unrouted()` returns `(stranded, routed)` now. The
half that is *not* fixed — `_DOC_DIR` regexes a whole table file, so a paragraph
of prose naming a path is the same characters as a row naming it — needs the
tables to parse as tables, and is written down at the site instead. The count
change is what makes it observable: the printed number moves when the matching
does.

### The name a template takes is a cost it charges its adopters

`cli/` is the most collided-with directory name a python monorepo has, and this
template claimed it. sky.boss adopted, found the collision, and resolved it the
only way then available: they moved **their own product** out of `cli/`. It cost
them 119 failing tests mid-flight and a `sed` whose worst artefact was
`from cli import cli` becoming `from x import x` — the rename reaching the click
group as well as the package, because the two shared a name.

`--shell-package` is the flag. It is a directory rename and nothing else, which
is the only reason it is cheap: **the package already never named itself.**
`_discover()` walks `__name__` and `__path__`, `__main__.py` imports relatively,
`scripts/paths.py` finds the directory by its `__main__.py`, and `tests/shell.py`
is where the tests reach it. Nothing in a generated tree spells the value, so
the flag renames a directory and no file changes meaning.

The name could not be **substituted** — `from {{SHELL_PACKAGE}}.x import y` is a
syntax error, so the template's own python would stop parsing, and an `ast` walk
over `template/` is how several gates here read it at all. Discovery keeps that
property; substitution would have cost the instrument.

**What the change actually found was in the generator, not the template.**
`bin/skeletor-verify` had five sites reaching for a literal `cli/`, one of them
a `from cli.test_cmds import SUITES` executed inside the scaffolded tree — the
exact construct `tests/shell.py` exists to forbid. The tool written to check
that a rename works was the thing that could not be renamed. Nothing could have
reported it earlier: with one possible name, a hardcoded name and a discovered
one are the same string, and *a value that has never been observed to disagree
with another value is undistinguished, not confirmed.* The asymmetry is what
makes it worth writing down — a hardcoded name in a **gate** does not fail as
"this gate is wrong", it fails as "the tree is broken."

**The flag is refused by `--set-arg`, and `--cli` with it.** An upgrade renders
two trees and merges them file by file, which is the wrong instrument for a
rename: the head render writes every file under the new name, so they arrive as
*new* files while the old ones are reported as no longer shipped and left where
they are, since this tool never deletes. Both directories then exist, and for
`--shell-package` the tree's own `scripts/paths.py` refuses to say which is the
shell. A rename is git's job; a three-way merge is for values **inside** a file.

sky.boss supplied the predicate that makes that a property rather than a list of
two names: **`--set-arg` is safe for an argument whose effect is *within* files
and unsafe for one whose effect is the *set of paths*.** The mechanical test —
whether `copy_overlay` consumes the value as a destination name — is how you
check it, not what it means, and a future flag will trip over the second while
passing the first by looking harmless.

### A constraint proven about one syntactic position, applied to all of them

`v0.22.0` shipped a `scripts/paths.py` that located the shell by walking for a
root `__main__.py` and raising unless there was exactly one. Its own comment
named the two-candidate case and called it *"worse than a wrong answer"* — and
treated it as the branch that could not happen.

It is the **ordinary** case. `__main__.py` is exactly what `python -m` needs, so
any adopter whose own product is a `python -m` CLI has a second one. sky.boss
upgraded and lost the entire toolchain: `paths.py` is imported by the CLI, by
every `scripts/check_*.py` and at pytest **collection**, so the failure was not
a wrong path but a dead tree — `./cli --help`, the suite, `check docs`, every
gate. They reverted to `v0.20.0`.

**It was not confined to `--shell-package`.** A tree that never passed the flag
broke identically, which makes it a regression against every adopter holding a
second `python -m` package rather than a rough edge on a new option.

**The root cause is a reasoning error worth naming, because the proof was
correct.** The name cannot be substituted into an `import` statement — `from
<token>.x import y` does not parse, and several gates read this template with
`ast`. True, established, and load-bearing. It was then carried to *every*
construct, and discovery was built for all of them. It was never true of a
**string constant**: `SHELL_PACKAGE = "{{SHELL_PACKAGE}}"` was legal the whole
time, and nothing in a generated tree imports *through* the name — the package
finds its groups by `__name__`/`__path__`, `__main__.py` imports relatively, and
`tests/shell.py` goes through `importlib`.

> A constraint proven about one syntactic position, generalised to all
> positions. The proof stays correct and the conclusion is wrong everywhere it
> was carried to.

sky.boss supplied the ordering principle: **an inference that can be ambiguous
must not outrank a record that cannot.** They proposed the record be
`.skeletor.json`; it is the rendered literal instead, for two reasons written at
the site before either of us needed them — the manifest is a **supported
deletion**, and `paths.py` reading its arg list would make the tree a second
reader of a format it does not control. A rendered literal is written by the
same render that created the directory and survives both.

**Why nothing here caught it, which is the sentence this template already had.**
Every fixture in `bin/skeletor-verify` is a fresh scaffold, so every tree the
grid has ever built has exactly one root `__main__.py`. CI was green on the
release; the 279-check grid was green on it. *A measurement over a population
that contains none of the subject is not a measurement of the subject* — stated
in `scripts/paths.py` itself, about `SCAFFOLD_MANIFEST`, two screens below where
this bug lived.

`product_package_gate` is the population fixed: a package with a `__main__.py`
skeletor did not write, committed the way a real product arrives, asserted at
the default name and a renamed one because the defect was never about the flag.
Planting the old discovery back turns 22 checks red and leaves every other gate
in the grid green — which measures both that the gate works and that nothing
else was ever going to.

### The command a gate names in its prose and has never run

`v0.23.0` shipped a tree that could not commit its own generated file. The lane
views' generator creates `.vscode/settings.json`, which is JSONC and tracked,
and `check-json`'s exclude still named `pyrightconfig.json` alone. Two adopters
hit it independently within a day — node-zero on an upgrade commit, stash.flow
on theirs — and neither could have been warned by anything upstream.

**The grid runs the linters. It has never run the hook set.** `black`, `isort`,
`flake8` and `pyright` are each invoked here with the arguments read out of the
generated tree's own `.pre-commit-config.yaml`, which is careful and is not the
same thing as running `pre-commit`. Every hook that is not a linter —
`check-json`, `check-yaml`, `end-of-file-fixer`, `check-merge-conflict` — had
been unexercised for this file's whole life.

The tell is the part worth keeping, because it is the opposite of a warning
sign. `bin/skeletor-verify` **names** `pre-commit run --all-files` in its own
prose, and names it accurately: *"the README's first command"*. It says so while
explaining an earlier bug that made that command fail in a node tree. So the
document that would tell you this file does not run it is the same document that
tells you how much it matters — and a reader who checks whether the grid knows
about the command finds that it does.

> **Naming a command in a gate's rationale is indistinguishable, from the
> outside, from running it.** The prose that establishes a command's importance
> is the prose most likely to be mistaken for coverage of it.

**And the enforcement was thinner than the hook.** `check-json` was reachable
from exactly one instrument: a local `git commit` by somebody who had run
`pre-commit install`. `ci.yml` does not run `pre-commit run --all-files` either
— it runs the linters directly against the same pins — and `check pre-push` does
not run hooks at all, which is why stash.flow's sixteen gates stayed green
through it. `bin/skeletor-new` makes the first commit with `--no-verify`,
correctly, because the hooks are not installed yet. So the failure is displaced
by exactly one commit: out of every population this repository can observe, and
into the adopter's, where it arrives looking like their mistake.

That changes what the right fix was. Widening the exclude answers the reported
bug and leaves tracked JSON with no blocking check anywhere. So it is the split
this repository keeps arriving at — **same artifact, two questions, two homes.**
`json_hook_gate` asks the generator's question: does the config I hand over work
for the file set I ship, in every configuration, and is every exemption still
earning its place. `tests/test_json_hook_covers_tracked_files.py` asks the
tree's: does *your* `.vscode/extensions.json` parse. The second carries the
`unit` marker, so `ci.yml` blocks on it — which is strictly more than the hook
ever did.

The gate is red on a tree scaffolded from clean `v0.23.0`, naming the file, and
green on the fixed template. A gate validated against the release it was written
for is worth more than one validated against a planted fault, and it was
available here only because two adopters reported before it was built.

#### The fixture set held the trigger and not the consequence

The same seam carried a second bug with a sharper population lesson.
`ensure_region` probed for emptiness with `head + "}"`, gluing the brace onto
whatever the last line was; when that line is a `//` comment — which `HEADER`
always ends in — `strip_comments` blanked the brace with it, the parse raised,
and the "somebody's hand-edit is mid-flight" fallback added a comma to a file
that was empty. Every fresh tree shipped a stray comma inside the final sentence
of its own header.

Its seven fixtures **contained the shape that triggers this** —
`"{\n  // only a comment\n}\n"` — and passed, because with no prior key a
spurious comma has nothing to fail to separate. The consequence needs a key
*and* a comment after it, and no fixture had both; the one test that pairs a key
with a comment puts the comment first, which is the safe order. node-zero found
it by having real editor settings.

> A fixture set can contain the input that reaches the bug and still be blind to
> it. **Triggering a fault and observing it are different requirements**, and a
> suite assembled by listing shapes tends to satisfy the first.

Two things followed from measuring rather than accepting the reported fix. The
proposed remedy — place the comma on the last line that is neither blank nor a
comment — is right and still breaks on a legal JSONC **trailing comma**, which
this file's own header tells the reader is allowed; found by running thirteen
shapes rather than the three under discussion. And asserting the file *parses*
does not catch the original bug at all, since a comma inside a comment is
invisible to the parser — which is exactly why it survived. The test names the
site.

### And the door a refusal does not cover: a new flag's default

Asked by sky.boss the same evening, holding a `v0.20.0` manifest, and it is the
better half of the finding:

> `--set-arg` refuses to change a path-set argument, and a new flag's default
> changes one for free. The refusal is about the loud path. A default is the
> quiet one, and the trees it reaches are exactly the ones that predate the
> thinking.

An upgrade renders the head from the *recorded* arguments, and a manifest
written before a flag existed has no value for it — so the parser fills in the
default. If `--shell-package` had defaulted to anything but `cli`, every tree
scaffolded before it would have had its entire shell package renamed on the next
upgrade, silently, with both directories left behind: precisely the outcome the
refusal exists to prevent, reached by an adopter who did nothing.

It defaults to `cli`, so nothing happened. **What had happened is that the gate
asserting so was looking at the wrong tree.** `shell_package_gate` checked the
default off a *fresh scaffold* — and a fresh scaffold **records** the flag, so
the recorded value is what every later render reads and the default is consumed
once, at scaffold time. The one path where the default decides anything is the
upgrade of a manifest that lacks it, and nothing exercised it. That is this
document's `--tagline` lesson at one remove: *a default no gate ever produces is
not a tested default* — and here the gate that named the default was green while
reading it from the recorded args rather than from its absence.

The fixture is a strip rather than an invention: delete the entry from a real
manifest, which is byte-identical to one written before the flag. The assertion
is `already current`, and it deliberately needs no knowledge of what the default
*is* — any other value is loud from both sides, because `cross_check`'s bijection
with the recorded hashes breaks on the rendered path and the offline path reports
every `cli/*` file as no longer shipped.

The operational rule, which generalises past this flag: **when adding a scaffold
argument that decides a path, its default is not a preference — it is a statement
about every manifest that predates it.**

**The first gate written for it was a tautology, and its own plant is what said
so.** The fixture scaffolded a tree with no `--shell-package` at all — a tree
that took the default, which is exactly what the population under test looks
like — then stripped the recorded entry and upgraded. With the default moved to
`shell` it reported `already current` while the gate beside it went red: the
same binary wrote the fixture and rendered the upgrade, so both sides took the
moved default, the disk got `shell/`, the render produced `shell/`, and
`cross_check`'s bijection held perfectly. A gate with the right label, a real
fixture, and no power.

The fix is that the fixture asks for `--shell-package cli` **by name** and only
then has the entry stripped, which pins the disk independently of the default.

That is a rule this document did not have, and it is sharper than the one it sits
next to. *The example you reach for first cannot discriminate* is about
convenience — the simplest fixture has the fewest ways to be wrong. This one was
not chosen for convenience; it was chosen because it looked like the honest
representative of the population. The tell is different and it is mechanical:

> **A fixture produced by the mechanism under test cannot test that mechanism's
> defaults.** The fixture and the subject came out of the same call, so they
> agree by construction, and the agreement is what the gate reads as a pass.

It is the *undistinguished, not confirmed* rule again — with one call producing
both sides, a correct default and a wrong one are the same green.

**sky.boss then ran that rule over their own suite and sent back the clause it
needs**, which is what stops it condemning every wiring test:

> **A fixture produced by the mechanism under test is acceptable exactly when
> that mechanism has its own gate that is not.** The failure is not the
> tautology; it is nobody having checked whether the second gate exists.

Their case: a route test asserting `body["block"] == tools_.block(...)`, the
expectation computed by the subject. It can only fail if the route stops calling
`block()` at all — and it is *correct*, because `block()` has an independent gate
one file over that walks `dataclasses.fields(Tool)`, so the expectation there
comes from the **type** rather than from the serialiser. The chain terminates in
something that cannot agree by construction. What I had built was a chain that
terminated in itself.

The clause matters because the tautology is often the *right* assertion. A route
really should return what its serialiser returns, and re-deriving the format in
the test would be a second opinion about it — the very duplication this shell
exists to prevent. The rule cannot be *never let the subject compute the
expectation*; it is **the chain has to terminate somewhere independent**.

**And the boundary needs one more line, because this repository has a gate that
looks like the defect and is not.** `manifest_args_gate` compares
`manifest_args(resolve(parse(argv)))` against itself replayed — both sides out of
the scaffolder, no independent source anywhere. It is sound, and the reason is
that a **fixed point is a law rather than a value**: it asserts *subject applied
twice equals subject applied once*, which is two different calls with different
inputs and can fail. `--reproducing False` is exactly what it failed on.

So the tell is narrower than "the subject computed the expectation":

> The tautology is **the expectation and the artifact coming out of the same call
> on the same inputs**, with no transformation between them that could differ.
> Two calls that could disagree is a law; one call compared with itself is a
> mirror.

My fix has the shape the clause describes, which is why sky.boss recognised it:
asking the fixture for `--shell-package cli` **by name** is the independent
terminus. The disk is pinned by something that is not the default, so the default
can move and the gate can see it move.

**And the heuristic sky.boss drew from two instances in their own suite**, which
is the part that tells you where to look before anything is written:

> The independent terminus tends to be the thing you reach for when you are
> trying to make a test **convincing**. The mirrors are what you write when you
> are trying to make it **complete**. The failure is having only the second kind.

Their two mirrors both terminate in something that is not the subject — a
dataclass's field list, and the stdlib's `utf-16-le` codec — and **neither
terminus was chosen with any of this in mind.** The second has the history that
makes the point: astral characters are one Python character and two JS code
units, offsets shipped raw for a week with both sides internally consistent,
because *the suite compared marks to marks and never sliced*. Only rendering it
in a browser found it. The fix was a test that **slices** rather than compares —
encode, cut at the converted offsets, decode, assert the emoji come back — which
puts the stdlib on the far side of the conversion where it cannot agree by
construction.

So the practical form is a question to ask while writing, not an audit to run
after: *would this convince somebody who thought the mechanism was wrong?* A
mirror never does, and it is exactly what completeness-driven writing produces.

**Audited here rather than accepted, because this is the tree that has a
generator** — sky.boss reported a structural null on the grounds that theirs has
none, so the mechanism has no seat there. Three gates checked by hand, not a
sweep: `versioning_gate` takes its omission set from `VERSIONING["tag"]` and
would pass over a wrong set, but terminates in the tag tree's own `check docs`
and unit suite, which hold no opinion about that map; `check_setup_blocks_agree`
compares a **rendered** floor against a depth this file measures independently
from the documents; `manifest_args_gate` is the law above. No instance found in
those three. The remaining gates are not claimed.

**And sky.boss then drew the line that keeps this out of the wrong drawer**,
which is the part worth carrying furthest. This repository keeps a family of
*facts no instrument at any distance the tree can reach can answer* — the
account's required contexts, the enterprise Actions permission, the operator's
tool version. This looked like a member and is not:

> An upgrade-time default is perfectly reachable. The instrument existed, it was
> green, and its label said the right words. It was **pointed at the wrong
> tree**.

The two want opposite remedies and filing them together loses both. A fact with
no reachable instrument is answered by **writing the limit down inside the
instrument**, so somebody reading a green row sees what it does not cover. An
instrument pointed at the wrong tree is answered by **moving it** — and writing
the limit down there would be a false comfort, documenting a hole that was
closeable all along.

**The tell is whether the case can be manufactured.** This one can, by stripping
the argument from a real manifest, and that is why the answer is a fix rather
than a caveat. It is the positive-control practice arriving from the other end:
when the live population cannot produce the case, a green render is not evidence,
and the move is to manufacture the case rather than look harder at the green.

The shape underneath is one this template already states one file away from where
it bit. `scripts/paths.py:171`, about `SCAFFOLD_MANIFEST`: *a measurement over a
population that contains none of the subject is not a measurement of the
subject.* A fresh scaffold records the flag, so the population of fresh scaffolds
contains no tree whose default is ever consulted — and the gate was confident
about exactly that population.

### The reference of a comparison is a choice, and an inherited one is a claim

`bin/skeletor-upgrade` prints a block headed *"file(s) skeletor wrote and you
have edited — standing state"*. It is computed by hashing what is on disk
against what skeletor produces, which is a sound comparison and was made against
the wrong side of it.

The list was measured against the **recorded** manifest, always, and the code
carried a comment arguing for that: computing it after the write loop would
"under-count exactly on the runs that changed the most". That is true if you
take an applied file to be a divergence, and an applied file is the opposite of
one — it was replaced *because* nobody had touched it.

The cost lands on the flow this tool documents. Run once, port the conflicts by
hand, re-run with `--ported`: on that second run every file the first run wrote
still differs from the base the second run has not yet replaced, so all of it is
listed under a heading asserting each entry is a decision the reader made.
node-zero measured 15 names with 11 of them the previous run's own output;
dream.doll watched the same list vanish on the next dry run, which is the tell —
standing state does not evaporate.

Both were separate trees, and neither reported a data bug: both verified the
manifest afterwards and it was correct. **The bytes were right and the sentence
over them was wrong**, which is this repository's most common defect and the one
no test of the mechanism reaches.

The fix names the rule: *measured against the base that will be in force when
this is read.* One function, `standing_divergence(target, reference)`, called
with the recorded manifest for a dry run or a held-back one, and with the head
render for a run that advances. `diverged` also joins the `--json` envelope,
because a consumer left to infer a field the report prints will infer the
version the report used to have.

Reaching it needed the fixture `pending_ref_gate` already builds — a real
version gap plus a real conflicting edit — and no other gate could. Every other
upgrade gate runs against a fresh scaffold, where nothing applies and nothing
conflicts, so the two candidate bases are the same map and the wrong one is
indistinguishable from the right one. The same fixture, for the same reason, is
why the manifest-advance bug lived to be reported from outside.

### A summary table inside the file it summarises

`ci.yml`'s header says the CI decision order is `.github/scripts/docs-only.cjs`
"and nowhere else", and it says so in a paragraph correcting an earlier sentence
that had claimed draft PRs run the gate job alone for five releases. Correcting
it corrected one of five homes. The claim survived in `AGENTS.md`, in
`.github/CONTRIBUTING.md`, in the comment the draft-discipline workflow posts
onto contributors' pull requests — and in a summary table inside `docs-only.cjs`
itself, 119 lines from the code it summarises, disagreeing with it.

That last one is the interesting one. It is in the file the surrounding prose
names as the single source, so it inherits that file's authority while being
prose like any other copy. A reader who follows the instruction — *go read the
script* — lands on the table before the code and has no reason to keep reading.

proto.pilot found all four survivors from an adopted tree and declined to fix
them locally, on the grounds that a prose divergence in a file the template is
actively revising is a permanent conflict. That is the right call and it is also
the general lesson stated backwards: **a statement is not fixed when its
authority is fixed, because the copies do not know they are copies.** The
partition gate `tests/test_pre_push_covers_ci.py` was built for exactly this
shape at a different artifact, and its own write-up records that fixing the
command's docstring left four restatements standing. This is that, again, with
one of the restatements living inside the authority.

No gate was added. A prose gate over five sentences in four languages has the
false-positive profile this repository has twice declined, and the honest move
is to record the drift where the next reader will meet it — which is now a
paragraph in `ci.yml`'s own header, beside the correction that missed.

### Zero of something can be a configuration, and sizing a scan says otherwise

`tests/test_pyright_deps.py` asserts that the environment pyright sees in CI is
declared in one file and is a superset of what the test jobs install. Both ends
of the scan were sized with `scanned()`, on the rule this repository states
everywhere: a negative assertion over an empty set is a tautology, and a green
one looks identical whether the thing did not happen or nobody looked.

The rule is right and it was applied to a set where zero is a legitimate answer.
A tree whose CI does not type-check has no jobs running pyright, and `least=1`
reports that as *the scan broke* — a sentence with the opposite remedy to the
truth. sky.boss hit it, and the escape as shipped was deleting the file, which
takes with it the superset rule that had **fired with a true finding
underneath**.

The discriminator is a fact the tree states rather than one the scan infers:
`.github/pyright-deps.txt` existing is the declaration. That gives a 2x2 whose
diagonal is the failure —

| | no pyright job | a pyright job |
|---|---|---|
| **no `pyright-deps.txt`** | this tree does not type-check in CI | a job checks an environment nothing declares |
| **`pyright-deps.txt` present** | a dead declaration | everything applies |

— and both non-failing corners carry a real assertion rather than a skip, since
`skip_budget.json` ships at 0 and a suite that goes quiet by emitting skips is a
ratchet failure wearing a configuration's clothes.

This is the `scheduled=False` split one registry over: one flag meaning both
*cannot run* and *nothing to run yet*, which expire differently and only one of
them silently. The tell is the same both times — **the only escape offered was
deletion**, and a rule you can only satisfy by removing it is describing the
wrong set.

### A gate that enforces a ruling can become the ruling's second home

`scripts/paths.py` argues at length that `docs/business-planning/` is
deliberately not narrative, and tells an adopter who keeps code-shaped proposals
there to append it to `NARRATIVE` — with a whole block on *why an append and not
an edit*, measured against `git merge-file`.

The gate written to hold that partition, `test_narrative_covers_lifecycle_folders.py`,
shipped its own `PRESENT_TENSE` dict carrying the same ruling with the same
reason. So the invitation was answerable only by editing a template-owned literal
inside a shipped test — the exact divergence the append seam exists to prevent,
one file over — and the test said so, in a failure message reading *delete the
entry*. dream.doll hit the classification half and stash.flow the staleness half,
independently, from real runs, on the same day.

Both halves of the partition now live beside each other in `scripts/paths.py`,
and the test reads them. Nothing about the checking changed.

What generalises is the direction of the mistake. The dict was not a careless
copy; it was written *by the work of building the gate*, because a gate needs its
exemptions in hand and the nearest place to put them is the gate. **A rule and
its enforcement are different artifacts, and the enforcement is where a second
copy of the rule gets created by people who know better** — the same reason
`.skeletor.json` records what the scaffolder did rather than what a second reader
of the format could reconstruct.

### Two absences with opposite remedies

`scripts/gen_vscode_queries.py --check` failed a missing `.vscode/settings.json`
with *"Create it with: python3 scripts/gen_vscode_queries.py"*. For an adopter
whose `.gitignore` predates the flag, that instruction is wrong in the
reassuring direction: creating the file makes the check pass, and the next fresh
clone is red again, because the file was never committable. mind.head reported
it; the gate's verdict otherwise turns on whether the machine running it has
opened the repository in an editor.

This template ships `.idea/` in `.gitignore` and deliberately not `.vscode/`, so
the collision cannot occur here — which is why the probe is a `git check-ignore`
question rather than a rule about our own ignore file. One subprocess separates
*the file has not been generated* from *this repository cannot keep it*, and
names two remedies instead of the wrong one.

Third instance of a shape this file already carries twice: the frontmatter
parser tolerating what it could not represent alongside what it could not find,
and `bin/skeletor-maintain` printing a green line for questions no registry
answered. **"It is not here" and "it cannot be here" are different answers, and
only one of them can be acted on.**

### The release that fixed a claim, and shipped a fabricated one

v0.25.0 corrected a sentence that had been wrong in five places. Its own commit
and the paragraph it added to `ci.yml` said *"proto.pilot swept all five from an
adopted tree."* proto.pilot swept none. Their report says, in as many words, that
they **declined** to fix them locally — a prose divergence in a file the template
is actively revising is a permanent conflict — and asked for the sweep to happen
upstream. The sweep happened here.

So a release whose subject was *a false statement with five homes* shipped a false
statement, in template prose, to every adopter, crediting an act to the tree that
had found the bug. They reported it back the next round.

Three things are worth separating out.

**It is a worse failure than the drift it was fixing.** A copy of a true sentence
starts out true and rots; this was never true. And it is unfalsifiable from
inside the repository — no gate can know what somebody else did in their own
checkout, so this is squarely a fact about the account rather than the tree, the
class this file already carries four instances of.

**The mechanism is that a synthesis got written as a quotation.** The workspace's
relay was scrupulous about the distinction, and the error is entirely downstream
of it: their report said proto.pilot *found* four survivors, *declined* to fix
them, and *left a note naming them*. Compressing that to "swept" is a plausible
reading of a helpful act, and it converted a decision the reporter had made and
explained into its opposite.

**The remedy is not care.** It is a rule with a test in it: *do not attribute an
act to a reporter without the sentence in their report that says they performed
it.* An attribution is a claim about somebody else's tree, so the evidence for it
has to be a quotation, not an inference — which is the workspace's own
attribute-quotes-label-syntheses rule, applied one step further out than they
applied it.

#### And the sweep made one tree strictly worse

The same commit replaced *"a draft PR runs the cheap gate job alone"* with a
sentence naming five jobs: `node`, `unit-tests`, `lint`, `integration`, `ui`.
That is accurate about this template and it is a claim about the **adopter's**
workflow — and sky.boss had already renamed theirs. They went from a sentence
that was merely wrong to one that was more precise and less true, in a file they
had diverged from and would now have to re-resolve.

> **Specificity is not a free improvement when the subject is somebody else's
> tree.** A vague sentence survives a rename; a precise one is a hostage to every
> identifier it names.

The fixed version names the *rule* — cheap jobs run, expensive ones do not — and
points at the one file that decides, because that file's path is the template's
own and its content is what an adopter would have to change on purpose.

### Two gates in one release, disagreeing about one file

`test_pyright_deps.py` was rewritten in v0.25.0 to stop treating "this tree does
not type-check in CI" as a broken scan. The new 2x2's remedy for a declared file
that no CI job installs was *delete `.github/pyright-deps.txt`* — and
`scripts/lint_pyright_gate.py`, the commit-time pre-flight shipped in the same
tree, requires every one of its sentinels to be reachable from that exact file.
Following the remedy turns a different gate red. sky.boss reported it; executing
it reproduces it in one run.

Neither gate is unreasonable alone, which is what makes the pair instructive:
each is right about its own consumer and neither knows the other exists. **The
reader is the only place two gates meet**, so a remedy is an assertion about the
whole tree even when the check that prints it is scoped to one file.

The repair was to ask a better question. Not *does CI run pyright* but *does
anything consume this declaration* — a workflow job or the commit-time hook —
which makes a tree that type-checks only at commit time a legitimate
configuration that keeps its file and keeps the superset rule governing it.

#### The same defect, one function down, in the edit that fixed it

The pyright side of that file had `least=1` and the test side had `least=2`.
v0.25.0 replaced the first with a partition, wrote a docstring about why sizing a
set whose zero is a configuration says the wrong thing, and left the second
alone. `least=2` made the whole file unsatisfiable for a tree with a single
pytest job, which is an ordinary layout. sky.boss had one.

The floor's stated reason was the fixture rule — with one job, *every test job*
and *this test job* are the same set, so a filter over them is unobservable. That
argument is about a **filter**, and this file has none: the rule loops over every
test job and exempts nothing. So the 2 was defending a discrimination the file
does not make, and it was inherited from a sibling rule where it was correct.

> **A number copied from a rule that needed it, into a rule that does not, is
> invisible precisely because it has a written reason.** Reading the reason is
> what stops you checking whether it applies.

### The reachability advice that was wrong about the ref it was handed

`--ref` exists so an adopter's manifest records a version somebody chose. Its
first release printed, on a real run, *"this checkout tracks no branch — whether
v0.25.0 is reachable cannot be determined"*, followed by a command grepping the
sha of the operator's own HEAD — a commit **past** the tag, which no pushed ref
identifies.

Both halves are the same mistake asked of the wrong subject. `tracks no branch`
is true of the detached worktree the flag itself creates: a fact about the
instrument, printed as a caveat about the tree. And the sha came from the live
checkout while the sentence named the pinned ref, so the sentence and the
actionable command described different commits — a reader following the command
concludes their pin is unreachable, which is the opposite of what pinning bought
them. **The flag's advice was most wrong exactly where the flag is most useful.**

node-zero and stash.flow each found one half. The line above the sha had been
moved to the render's checkout in the same commit and this one had not.

What this repository had already written down, one paragraph from the code:
*a predicate right about what it measures, wired to prose that claims more.* The
ruling that shipped it said the warning was "the right question for a tag" — true
of the question, and never checked against the sentence.

#### The gate for it was green with both defects planted back

Worse, and the useful part. `pinned_ref_gate` grew two assertions for exactly
these, and both plants left it green: the advice is on the **writing path**,
withheld from a dry run on purpose, and the gate's fixture was `--dry-run`. Two
negative checks over output that could not contain the string either way.

That is *a negative assertion over a set nobody proved non-empty* — this file's
own rule, stated for `filesAnalyzed` and for the lint gates — arriving inside the
gate written to catch a defect of the same shape. The fixture is a real run now,
and a **positive** assertion that the advice was printed at all is what keeps the
negatives honest.

One of the three plants still passes, and the gate says so rather than pretending
otherwise: reverting the sha to the live checkout changes nothing observable,
because under `--ref` that sha is no longer printed. The branch is what repairs
the finding, the branch's removal is caught, and a check that cannot fail was
deleted rather than kept for the look of coverage.

### A predicate that could not mean what its sentence promised

The v0.25.0 upgrade began naming *"divergences this release also changed"* under
the label *worth re-asking whether your version is still needed, or was the thing
we took*. Six trees split two-and-two, and they were not disagreeing about the
same thing: proto.pilot named five with two genuine adoptions and asked for it not
to be tightened, dream.doll saw four of fourteen with no false positives, and
sky.boss saw four with zero adoptions and read it as noise.

All four are one predicate behaving correctly. It computes *file you diverged on
∩ file this release changed*; the label promises *adoption*, and *because of your
divergence* is intent, which is not in the bytes. The two coincide when the
release touched the file because of the divergence and come apart otherwise —
which is why the trees with real adoptions found it useful and the tree with none
found it noise.

The predicate stays and the sentence shrank. Tightening would miss real
adoptions and fail in the reassuring direction, since fewer rows read as nothing
to re-ask. **When a computable set is a proxy for an uncomputable one, the honest
move is to name the set and let the reader do the inference** — the same reason
`blocked_on` and `queue_order` are read only from explicit lines and never
guessed.

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

## A true clause is how a false one gets through, and scrutiny is what it spends

`CLAUDE.md` already carries the shape: **the dangerous form is a false clause
conjoined to a verifiable one**, because the reader who accepts the invitation to
check verifies the checkable half and banks the conjunction. It is written there
about template prose. This is the same form in a cross-repo message, twelve hours
after the commit that named it, and what is new is the remedy.

The claim was three clauses: *clean at one blank line, clean at two, `exit=1` for
all three spellings when a marker is introduced.* The first two were right. The
third was measured on a harness anchored on the wrong line — the closing brace of
a literal rather than the end of the comment block below it, which in the previous
release were four lines apart and are now thirty-two, because that release
inserted a block into exactly that gap.

It went to skyrow-workspace, who **checked the first two clauses, found them true,
and relayed all three**. They then withdrew an escalation that had already reached
the person who would have paid for it.

Their statement of the remedy is better than the one this repository had, and it
is theirs:

> The countermeasure is not scrutiny, because scrutiny is what the form consumes.
> It is re-deriving the claim by a route that does not pass through it.

They then executed it — rebuilt the harness from scratch, derived the anchor
programmatically rather than copying mine, and reproduced the corrected rows
exactly. Two routes, one answer.

**And the corrected answer was still wrong, which is the clause worth adding.** A
route that does not pass through the claim can still pass through a shared
*premise*. Both harnesses used base `v0.25.1` because both of us were reasoning
from "the six trees have their base held back" — and all six manifests read
`v0.26.0`. At this seam that is not a detail: it is the 28-line block again, so
the two bases put a test append on opposite sides of the text the template keeps
editing. The third route — running the real tool against the six real checkouts —
put the measured cost at one tree rather than six.

So: **independence of method is not independence of premise, and the premise is
the cheaper thing to check.** One `json.load` per tree settled what two
independently-built harnesses agreed on and got wrong.

The local tell is worth keeping too, because it was in the output and was walked
past. The rebuilt harness reported the adjacent case *clean*, contradicting a
measurement made an hour earlier — and **a harness that no longer reproduces the
defect it was built from is not measuring the defect.** A disagreement between two
runs of your own instrument is a finding about the instrument before it is a
finding about the subject.

## The trees with nothing to count are the ones that mattered

v0.27.0's region was priced by counting conflicts across six adopter trees, twice
— once here and once by skyrow-workspace, with different harnesses. Both counts
were right. Both conclusions about **placement** were wrong, and the three trees
that found it are the three that conflicted zero times.

The claim was that an existing append which merges cleanly ends up *below* the
arriving marker, so nobody has to move anything. git orders two additions at a
shared anchor rather than colliding on them, and which side yours lands on depends
on exactly where it sat. dream.doll merged cleanly and landed **above**; mind.head
found the same from a tree that did conflict. dream.doll's own sentence is the
indictment:

> The six-tree measurement behind the cost estimate would not have caught this,
> since it counted conflicts and this tree has none.

**A conflict count is a measurement of the trees that conflict.** The failure mode
here is the reverse of the usual one: not a sample too small, but a sample whose
selection criterion is the thing that hides the defect. Every tree with the bad
outcome was, by construction, in the half the instrument discarded — and the bad
outcome is silent, because an append above the marker keeps the pre-region
behaviour while every signal says it is covered.

Three things this repository already knew, arriving together:

- **A negative over a filtered set is a claim about the filter.** Stated here for
  `filesAnalyzed` and for lint gates asserting they enumerated the tree. A
  conflict count is the same shape one level up: zero conflicts is the *absence*
  the instrument reports, and absence of the measured event is not absence of the
  hazard.
- **Undistinguished, not confirmed**, applied to a harness instead of a flag. The
  placement claim also carried *"measured across five offsets"* — and those five
  offsets returned an identical answer five times. An identical answer across
  every value of a parameter is the tell that the parameter varied nothing.
  proto.pilot reached the same conclusion from outside with three probes, and
  declined to assert it because they could not see the harness. They were right:
  a first-merge probe cannot distinguish the layouts, because the region buys
  nothing on a first merge. It buys the re-run, and only the re-run.
- **A claim a tree can check should not be a claim a tree is asked to believe.**
  dream.doll asked for a test rather than a corrected sentence, which is the right
  trade and the one this file keeps arriving at from other directions. Placement is
  a fact about the adopter's own file, so
  `tests/test_narrative_covers_lifecycle_folders.py` settles it locally and no
  release note has to be trusted. The corrected prose still ships, because a check
  says *what* and the reason says *why* — but the check is what makes it safe.

**The same release named two seams and shipped the region to both, and there were
three.** `check_doc_links.py`'s `SCAN_ROOTS` kept the blank-line rule for another
release; proto.pilot found it with `git grep`. Rule 2 says never introduce a list
where a pattern will do, and a fix that enumerates its sites is a list wearing a
diff. `append_seam_gate` enumerates seams by their invitation now — a file that
tells an adopter to add something *as an append* is a file with a seam — so a
fourth arrives covered or arrives red.

**And the pronoun.** The dispatch carrying these fixes said to resolve two
conflicts as *take ours*, which is right from the template's seat and reverses
across exactly the boundary a relay crosses: one of the two was the adopter's
truthful local rewrite, which the same message separately said to keep. sky.boss
caught it by ignoring both instructions and reading the sidecar patch. Their line
is the durable one — **which files conflict is cheap to predict from outside and
travels well; how to resolve one does not travel at all**, because the resolution
is a fact about the fork's reason and the reason lives in the tree that wrote it.
Name the side, never the pronoun, and prefer not to prescribe a resolution at all.

## A safe position inside prose is safe for one release

The region fixed the wrong half. It gave the adopter a marker to append below, and
put the marker at the **top** of its explanation block — so "below this line" named
a position with ninety lines of template prose under it, and the prose is the thing
a release rewrites.

proto.pilot measured two positions against one release and got a clean answer:
just under the marker re-conflicted, the foot of the prose was clean. Reproducing
it against the next release got the inverse — the foot re-conflicted and just
under the marker was clean. Both readings were correct. Systematically, with
`git merge-file` over the rendered file, varying which line upstream edits:

    upstream edits    adopter's append at
    the line N        1 above   2 above   3 above   below the rule
    above the rule    the rule  the rule  the rule
    ──────────────────────────────────────────────────────────────
    N = 1             CONFLICT  CONFLICT  clean     clean
    N = 2             clean     CONFLICT  CONFLICT  clean
    N = 3             clean     clean     CONFLICT  clean

Read the last column first. **Below the rule is clean whatever upstream edits**;
every other column is the interaction of two numbers, one of which is a fact about
the next release. So the advice was not merely imprecise — it was *unwritable*, and
the two anecdotes that looked like a contradiction were the parameter being varied
one value at a time.

The remedy is a **frozen terminator at the bottom of the block**: the rule is the
template's last word in its section, nothing rendered ever goes below it, and the
explanation — which does get rewritten — sits above it where it cannot be adjacent
to anybody's append. The separation stops depending on which paragraph a release
happened to touch.

**Measured cost, against the six real trees at their real recorded base.** Four
extend `scripts/paths.py`; two of those four conflict on it once, and which two is
*not* a function of how far down the append sits — one conflicting append is two
lines above the old block's end and two clean ones are three. It is a function of
which prose this release rewrote next to them, which is the argument for the move
restated as a bill.

### Three ways the check for it did not bite, and one is Rule 2 eating itself

- **It covered one seam of two.** The test hardcoded `scripts/paths.py` and five
  `paths.py`-shaped regexes, while the generator discovered its seams by their
  invitation. dream.doll's line: *the generator discovers its seams and the adopter
  is handed a list of one.* They measured `SCAN_ROOTS += ["src"]` immediately above
  `check_doc_links.py`'s marker and got 211 passed. Rule 2 says never introduce a
  list where a pattern will do, and the artifact that had one was the artifact
  enforcing the rule.

  Both ends are discovered now. Seams come from the same invitation predicate the
  gate uses; the constants come from each seam's own documented examples; and the
  appends come from an `ast` walk rather than a regex, so *which statement extends
  a seam constant* is answered by syntax. One predicate serves both populations —
  run over the examples it says what a seam invites, run over the body it says what
  is an append — and a name in a value position is excluded by construction rather
  than by exemption.

- **It did not bite where it did cover.** The region held ~57 lines of prose, and
  the assertion was *below the marker*, which the whole measurement above shows is
  not the property that matters.

- **The detector spelled its own needle.** Assembled contiguously, the test file
  matched its own seam predicate and the suite failed reporting itself. Assembling
  the string from parts is what `checkout_path_literal_gate` already does for
  exactly this, and the alternative — an allowlist entry for the detector's own
  source — is the second entry that means the predicate is wrong.

### The control could not be a chosen offset either, and the first fix was clean

`append_seam_gate`'s discriminator is a pair: an append below the rule must survive
a re-run, and the same append at the foot of the prose must not. That control had
been anchored on a literal line of the seam's prose twice, and both times the
release that changed the seam rewrote it — an honest `could not place` failure, and
still a gate that had stopped testing. The obvious repair is a structural offset,
and the table above says why that is wrong too.

So the position is **found**: scan upward from the rule for the nearest place that
is clean on the first merge and conflicting on the re-run, using `git merge-file`
as a cheap oracle over the same texts the real tool will merge, then verify with
the real tool. Both conditions are load-bearing — one that conflicts immediately
never reaches the re-run, and one that is clean twice is the subject wearing the
control's label.

**Building it found that the upstream edit was the wrong shape.** A *reword* of the
seam's last line cannot make a re-run conflict at all: after the first merge the
tree already holds the reworded line, so the second merge finds both sides agreeing
about it. Measured across every offset, a reworded tail gives `clean, clean`
wherever it gives a clean first merge, and the gate spent a run reporting exactly
that — no control was placeable. An **insertion** at a shared anchor is what
actually happened to the trees that found this (v0.26.0 put 28 lines into that
gap), and it is what discriminates. The fixture inserts a paragraph now, through
the same helper the oracle selects against, so the control cannot be placed against
one change and verified against another.

### A comment-shaped regression passes a comment-skipping check

The region assertion skipped comments, because an adopter's append is code and the
frozen block is comments. So a release adding a *paragraph* below the rule passed
it while doing the one thing the rule forbids — which is not hypothetical, it is
the layout that shipped for two releases. Below the rule there is now one comment
run and then nothing but blank lines, and planting a paragraph below the frozen
block turns the gate red.

**What is not asserted, said as a limit rather than left implied.** "Frozen" is a
promise about future releases and there is no population to check it against yet:
no released tag carries this block, so an across-tags assertion would pass
vacuously today. What is checkable now is that the promise reads identically
wherever it is made — the two seams are each other's control — and a seam whose
block has drifted is a seam making a different promise.
