# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this repository is

**skeletor is a generator, not an application.** Nothing here runs in production;
everything here is *copied into* a new repository by `bin/skeletor-new`, with
placeholders substituted. The output is a project that governs itself from its
first commit.

### How it is invoked in practice

Three entry points, all leading to the same `bin/skeletor-new` call:

| Entry point                       | Used when                                               |
| --------------------------------- | -------------------------------------------------------- |
| `/new-project` skill              | The user says "set up this project using skeletor"      |
| [`AGENTS.md`](AGENTS.md)          | The user points an agent at this repo directly          |
| `bin/skeletor-new` by hand        | The user runs it themselves                             |

**[`AGENTS.md`](AGENTS.md) is the procedure, and it is the only copy of it.**
`.claude/skills/new-project/SKILL.md` is a pointer at it: frontmatter, a
`SKELETOR=` line, and an instruction to go read it.
`bin/skeletor-install-skill` copies that pointer to `~/.claude/skills/`,
rewriting the `SKELETOR=` line to wherever this checkout actually lives — and
verifies the rewrite happened, because `sed` matching nothing exits 0 and would
leave the skill aimed at a path on nobody's machine.

This used to be two renderings of one procedure with an instruction to keep them
in sync, and the instruction lost. `bin/skeletor-install-skill` made the drift
worse by adding a **third** copy that nothing revalidates: a snapshot in the
user's config directory that goes stale the moment the procedure changes and
that no gate here can see. It went stale exactly that way, and kept handing
agents a `--no-git` flag that had been removed for leaving scaffolds with no git
repository at all.

So the rule is structural now rather than remembered: **do not put a procedure
step in `SKILL.md`.** The only thing an installed skill knows that this
repository cannot is where this checkout is, and that is the only thing it
should carry. Anything else belongs in `AGENTS.md`, which both entry points
read, and which locates itself — it says `$SKELETOR`, never a written-down path,
because a path in prose is wrong for every checkout but the one it was authored
on.

Every mechanism here was extracted from one mature production repository and is
recorded in [`docs/DESIGN_RATIONALE.md`](docs/DESIGN_RATIONALE.md) with the
incident behind it. When you are deciding whether a rule earns its place, that
document is the evidence, and it is the thing to update if you conclude a rule
does not.

---

## Commands

```bash
# Scaffold a project (the only "build" this repo has)
bin/skeletor-new ../target --name "Name" --cli xx --tagline "..." --tier core
bin/skeletor-new ../target --agent none          # no Claude tooling; rules still ship
bin/skeletor-new --help

# Verify a template change end-to-end — run this after ANY edit under template/
bin/skeletor-verify                    # every tier x every language
bin/skeletor-verify --tier core --keep # one tier, trees left behind to inspect

# How far behind are the versions we start other people's repos on?
bin/skeletor-check-pins

# Apply one of those reports — every location of a pin, or none of them
bin/skeletor-bump pyright 1.1.413 --dry-run
bin/skeletor-bump pyright 1.1.413

# The weekly pass: is CI green, is anything stale, and hand the work over
bin/skeletor-maintain            # docs/MAINTENANCE.md is the procedure
bin/skeletor-maintain --agent

# Carry a template change into an already-scaffolded tree
bin/skeletor-upgrade ../target --dry-run
bin/skeletor-upgrade ../target
```

There is no test suite for skeletor itself. **The scaffold IS the test**: a
template change is verified by generating a tree and running that tree's own
gates. A scaffold whose first check is red teaches the user that red is normal,
so "a fresh tree passes its own gates" is the definition of done here.

`bin/skeletor-verify` is that procedure, executable. It generates every tier
against every language — a placeholder that only appears in the `node` overlay
is a `render()` failure a user would otherwise find first — and against each
Python tree runs the unit suite, `check docs`, `check merge-drivers`,
`check output`, a `--help` group-registration check, a static check that every
`script()` call in the tree's CLI names a file that exists, a check that the
generated README's Setup block runs every tool by path, a check that the tree is
its own repository at its first commit, the tree's own `test <marker>` command
for every suite a scaffold ships no tests for, the lint hooks, pyright, and
`actionlint` over the workflows the tree ships.
eslint and prettier run once, on the fullest tier's `both` tree, and the fullest
tier is scaffolded a second time into a deliberately long path and a third time
into a directory that already has files in it.

**Tier composition is checked across all 18 configurations at once**, which is
the one question no tree's own suite can ask. stash.flow reported the class: two
`core` files cited `tests/test_state_paths.py`, which shipped only at `agentic`,
so a `core` reader following either citation found nothing. Inside one tree a
reference either resolves or does not; the defect is that it resolves in a
*different* one, and that is the generator's question.

The predicate is what makes it allowlist-free: a reference is a finding only
when it is **absent here and present in a configuration that ships strictly
more**. A file the user is told to create, a URL, another repo's path — all
absent everywhere, so all out of scope by construction rather than by
exemption. Containment is read from `TIERS`, `LANGUAGE_OVERLAYS` and `AGENTS`,
so the language and agent axes came free, and the agent axis is where it earned
itself: `--agent none` shipped a `.github/DOCS_INDEX.md` routing readers to
three paths under `.claude/`, which that flag exists to omit. The tree's own
`check_doc_tables.py` cannot see it — that one walks `docs/`, and `.claude/` is
not in `docs/`.

Eleven findings on the first run, six distinct sites, and every one had a fix
better than an exemption: four were live citations sending a `core` reader to a
module only `agentic` ships, two were history about the repository this was
extracted from. There is no allowlist and no mechanism to add one. What it
cannot see is written down instead of guarded — another repo's path that
*collides* with one of ours reads as a local dangling reference, which is how
jam.sense's `cli/worktree.py` surfaced.

That empty-suite gate named `integration` until it had to name two things. A
suite whose tests a scaffold cannot ship is red on arrival unless the CLI
tolerates an empty selection, and the gate is what proves the tolerance — so
when `ui` arrived taking the identical code path, the gate would not have
noticed either way. It reads the tolerant set out of the tree's own
`cli/test_cmds.py` now, and fails when that set comes back empty, since a loop
over nothing passes every assertion inside it. The `ui` marker itself shipped
with no job selecting it, which is a hole of a different shape and is written
up in [`docs/DESIGN_RATIONALE.md`](docs/DESIGN_RATIONALE.md): a marker is how a
test joins a suite and equally how it leaves CI, and only one of those is
visible.

Its **exemption** then had the same shape as the bug, twice over, and both are
worth knowing before touching that registry. `release-please` carried `ui` in
its `needs:` while the docs said to delete the job — and a `needs:` naming a
job that is gone is a `startup_failure`, so zero jobs run, no logs exist, and
nothing on the commit names the line. `actionlint` catches it here and cannot
help there: the failure happens in a tree that edited the file, which only a
shipped check reaches. And `scheduled=False` meant both *cannot run* and
*nothing to run yet*, which expire differently — the second silently. The reason
is data now, and naming `empty` makes the tree assert its own emptiness.

The generalisation, proto.pilot's and the reason two of these are one class:
**a flag that has never been observed to disagree with another flag is
undistinguished, not confirmed.** Three registry rows cannot tell two booleans
apart; the fourth is where the coincidence shows. Both splits here —
`ships_tests` out of `scheduled`, and the reason out of `scheduled=False` —
were made on that row.

The two newest are the **setup path**, which this file's own gates had never
once executed. Everything above verifies a tree that is already installed —
`make_venv` builds one shared venv and symlinks it in — so the commands a reader
actually runs first were the only part of a scaffold nothing checked, and both
of them shipped broken.

The README said `pip install -r scripts/requirements.txt && pre-commit install
--install-hooks`. On any distribution carrying an `EXTERNALLY-MANAGED` marker —
Arch, Debian 12+, Ubuntu 23.04+, Fedora, Homebrew macOS — pip refuses outright
under PEP 668, so line one of the file that exists to onboard a reader exited
non-zero, which reads as user error at the exact moment they cannot tell.
Everywhere else it installed system-wide and `pre-commit` was then not on PATH
at all. That gate is deliberately **static** rather than a real install:
executing the block would have caught this here and never on a CI runner, whose
`setup-python` is not externally managed, so the rule — every tool run by path,
with `npm` the one allowlisted PATH lookup — is what makes the two agree.

The repository gate is the one that had to be paid for twice. `--no-git` reads
as the careful flag for scaffolding into a repo that already exists, and it is a
no-op in precisely that case: the scaffolder skips a tree that has a `.git`
regardless. It only ever bit the empty directory it looked safest in, and the
documented invocation carried it — so `isort`'s `skip_gitignore`, which shells
out to `git ls-files`, opened the first `check pre-push` a new user ever runs
with `fatal: not a git repository`, three times, on the run the setup guide
prescribes specifically to show that a scaffold is green. The merge driver, whose
definition lives in `.git/config`, could not be installed at all. `bin/skeletor-verify`
never saw any of it because `scaffold()` does not pass `--no-git` — the
verifier and the documentation disagreed about the command, and the verifier was
right. The docs no longer say it.

That gate also asserts git resolves the tree to *itself*, which is the half that
would have gone unnoticed: a tree generated inside another repository has git
answering every question about the parent, so `check merge-drivers` passes by
reading a driver installed for something else entirely.

`actionlint` is the same shape of hole one layer out: four workflows ship —
`ci.yml`, `docs-validation.yml`, `pr-draft-discipline.yml`, and
`coverage-nightly.yml` from `governed` — and not one had ever been executed, or
read by anything that understands Actions. `tests/test_ci_draft_gate.py` asserts
the load-bearing pieces of `ci.yml` with a regex over the text, which catches a
trigger somebody deleted and nothing about whether the file is *valid*.

It is the one lint that does not read its arguments out of the tree's
`.pre-commit-config.yaml`. Two reasons are available and only one survives —
the tree has no actionlint hook to read (true today, falsified the day one
ships) and this gate is not asking the tree's question at all (true whatever
ships). The second is the load-bearing one, and they are kept apart on purpose,
because the first kind expires without anything going red. The asymmetry is
the point: black, isort, flake8 and pyright ask whether the tree
governs itself, and are read from its config so the answer is the tree's own.
This asks whether what skeletor ships is valid at all — `check_no_baked_paths`'s
question, equally not the tree's business. Adding actionlint as a hook in the
generated tree would be a different and also good change, since it would check a
user's own edits to those files.

Both halves of its scope were measured rather than assumed, by planting each
case. It catches a malformed expression, a `needs.<job>` naming a job that does
not exist, a renamed job output, an unknown runner label, and the `run:` blocks
where shellcheck is on PATH. It does **not** catch an action reference that does
not resolve: `actions/checkout@v99` passes it green, because knowing better
takes a network call. Whether shellcheck was present goes in the gate's label,
because actionlint skips those blocks silently when it is not — the pyright
lesson, in a different tool.

Those last two are each a bug that shipped. `script()` joins its argument onto
`PROJECT_ROOT`, so `script("-m", "pytest", ...)` became the path `<root>/-m` and
made `check pre-push` — the first command the scaffolder tells a user to run —
impossible to pass at any tier; `module()` now exists so a flag has its own
door. And the long path exists because `black` rewrites an over-long string
assignment only when the parenthesised form would fit, so an absolute path baked
into a source line is red for one band of checkout depths and green either side
of it: the length there is derived from the tree's own line limit rather than
picked, and a round 120 sat past the band and caught nothing.

The README badge row is gated in both directions, because both directions are
the same bug: a default scaffold must open with title, blank line, tagline and
no badges at all (`--org` defaults to `OWNER`, which names no repository), and
an `--org` scaffold must carry a CI badge pinned to the *release* branch (a
badge answers "should I expect this to work", which is a question about what was
released). A badge that is broken or permanently grey is a gate that is red on
arrival wearing a cosmetic hat.

That pin was originally load-bearing for a stronger reason — `ci.yml` had no
`push` trigger for the branch `git init -b` creates, so a bare badge read "no
status" forever. proto.pilot found what that trigger actually cost: a repo that
commits straight to its base branch, which every project does while it is one
person, ran no CI at all, and three commits landed before anybody noticed,
because "no workflow ran" and "the workflow passed" are the same absence of red
from the terminal. The base branch is in the `push` trigger now. The badge stays
pinned, but on the weaker of its two reasons, and both are written down so the
next reader can tell which one they are holding.

The **populated tree** is the newest, and it is the first gate here that an
outside consumer wrote the bug report for. Every other tree is generated into a
fresh directory, where every file present is by definition skeletor's — so
`.skeletor.json` was only ever built on the one path that cannot tell the two
apart, while `--force` into a repository somebody already works in is the path
[`AGENTS.md`](AGENTS.md) calls *the usual case*. `tree_hashes()` walked the tree
and recorded whatever it found. proto.pilot, the first real consumer, got a
manifest of 228 files of which 114 were its own product source, its tests, a
build artifact and a gitignored `prototypes/` tree.

What that cost is worth being exact about, because the guard held: it did **not**
overwrite anybody's source. `cross_check` refused, correctly and permanently —
114 files "recorded, but the base render does not produce it" — so the damage was
that `bin/skeletor-upgrade` was unusable, forever, on precisely the trees it
exists for, and said so in a message that reads like the *tree* is at fault. The
mechanism was right; the manifest it was handed was wrong.

The manifest now records what the scaffolder **did**, not what is on disk:
`copy_overlay` already reports every file it renders, and the post-copy steps are
found by hashing the tree either side of them. Neither half is a list — naming
the four files `regen.py` currently writes would go stale the next time it learns
to emit an index, and silently, since a file missing from the manifest reads
exactly like a file the user edited. A collision *is* skeletor output and stays
recorded, which is why "everything that was not here before" is the wrong rule.

The gate asserts the recorded set by **recomputing** it — the same arguments
scaffolded into an empty directory, and the two manifests must have identical
keys — rather than listing the decoys it plants. It then runs the upgrade, and
both assertions are load-bearing: the comparison is two readings of the same
scaffolder, so a manifest that under-records leaves both sides equally short and
stays green, and only the upgrade's independently rendered base catches that
direction. Each was established by planting the bug it claims to catch. Two
copies of a mistake agree with each other — which is the whole reason a gate
built on a fresh directory could not see this one.

Three things it reads rather than repeats: the tier and language lists come from
`bin/skeletor-new`, the lint arguments from the generated tree's own
`.pre-commit-config.yaml`, and the tool versions from
`template/core/scripts/requirements.txt`. A copy of any of them would verify the
template against a config the template does not have — and would stay green
while doing it.

The lint gates exist because their absence shipped: a scaffold once carried 19
files `black` would rewrite, 20 imports `flake8` rejects, and markdown
`prettier` re-pads. `pre-commit run --all-files` — the first command the README
gives a new user — was red on a tree nobody had touched.

They pass **explicit filenames**, because that is what pre-commit passes and the
difference is not cosmetic. flake8 applies its `exclude` list when it walks a
directory and ignores it for a file named on the command line, so `flake8 .` and
the hook answer differently about precisely the files somebody excluded. This
gate ran against `.` and was green while a `docs` entry in `.flake8` — matched
against every path component, so it also silenced `scripts/docs/` — hid four
dead imports that failed the user's first commit. There is now no `docs` entry:
flake8 only ever reads Python, so it never spared a file, and excluding nothing
is what makes the two gates agree. A companion check asserts the enumeration
found the tree, since a lint over zero files is green and worth nothing.

`pyright` was for a long time the one hook not gated here, exempted as a node
package wearing a Python name whose toolchain was not worth the minute. The
minute was never measured. Its pip wrapper caches node in
`~/.cache/pyright-python` **keyed by version — once per machine, not once per
tree** — so the real cost is a cold download on a fresh runner (67MB), a
re-download on every pin bump, and about 1.1s per tree after that. Three Python
trees, three and a half seconds. It is gated now, from the same
`requirements.txt` pin as every other tool, and it reads its own arguments out
of the generated tree's `.pre-commit-config.yaml` — which names them with
`entry:` rather than `args:`, so it needs its own reader.

What the exemption bought, while it lasted: `commit()` reassigned its own
`paths: tuple` parameter to a list, and the resulting errors shipped red in
every `governed` and `agentic` scaffold while this file stayed green. `f1f75ab`
fixed that, and it is history rather than a standing red — a `governed` tree is
clean under `pyright==1.1.411`. Reintroducing it now turns `governed` and
`agentic` red and leaves `core` green, which is the tier signature you would
expect, since `core` ships no `cli/commit.py`.

Three things that gate is careful about, all of them the failure this file
exists to prevent. It asserts `filesAnalyzed`, because pyright prints `0 errors`
just as cheerfully when its `include` paths match nothing. It is the one gate
that does not use `run()`: `--outputjson` writes its report to stdout and its
complaints to stderr, so merging the streams makes the JSON unparseable at
exactly the moment it carries the explanation. And it passes **`--pythonpath`**,
which is the difference between a check and a coincidence.

That last one shipped broken and CI caught it within the minute. pyright
resolves imports against an interpreter it finds on PATH; it does **not** read
the tree's `.venv`, symlinked or otherwise. So the gate checked whatever python
the machine happened to offer. This developer box has `click` in
`/usr/lib/python3.14/site-packages`, so every decorator resolved and all three
tiers were green; the CI runner's `setup-python` has no `click`, so
`reportMissingImports: none` left `click.group` unresolved, every
`@group.command()` became an attribute access on an undecorated function, and
`core`, `governed` and `agentic` came back with 24 errors apiece. Same tree,
same pyright, opposite answers, decided by a package nobody installed on
purpose — which is exactly what `pyrightconfig.json`'s own comment warns about,
and it prescribes the remedy it does: *reproduce a CI result with
`pyright --pythonpath <the CI interpreter>`*. Reproduce that condition locally
by putting a click-free interpreter first on PATH; without `--pythonpath` it
fails identically to CI, with it the two are indistinguishable.

A toolchain that cannot be fetched is skipped **loudly**, never silently.

**Never run `black` directly on `template/`.** It sees `{{PLACEHOLDER}}` rather
than the value it renders to, so its line-length decisions are made against the
wrong widths — and a line near the limit then formats one way here and the other
way in a real tree. Fix black findings by scaffolding a tree, running it there,
and porting the change back. `bin/skeletor-verify` is what tells you the truth.

isort used to have the same problem for a different reason and no longer does:
`.isort.cfg` at this repo's root names `cli` and `scripts` as first-party, which
they are not *here* — they exist only under `template/<overlay>/` — so without it
isort read them as third-party and stripped the blank line before `click` in
twenty files. Keep that file in step with `template/python/pyproject.toml`.

Always run all tiers when a change touches `template/core/`, since `governed`
and `agentic` compose on top of it. That is the default; `--tier` is for
narrowing a debug loop, not for a final check.

`bin/skeletor-upgrade` is how a template change reaches the repositories
already generated from one. It renders the tree's **base** — skeletor at the
`skeletor_ref` in that tree's `.skeletor.json`, run with the arguments it
recorded — renders **ours** from this checkout, and three-way merges against
what is actually there. A file the user never touched is replaced; one they
edited is merged **only if the merge is clean**; a conflict leaves the file
exactly as it was and writes the template's own diff to `tmp/upgrade/`. A
conflict marker is never written into somebody's tree, nothing is committed,
and a file the template stopped shipping is reported rather than deleted.

`tmp/upgrade/` describes **one** run. That took a bug report to arrive at, from
proto.pilot, who could see it and this repository could not: the conflict and
collision reports are the only place this tool tells a reader to go *open a
file*, and both sentences shipped unconditional. A `--dry-run` printed "what the
template changed in each is in `tmp/upgrade/<path>.patch`" and wrote nothing
there — while the directory sat holding a four-day-old patch from a real run
against a template HEAD that had since moved. The two facts were each true and
the output contained no way to hold them together.

Both halves are now fixed, because they are the same bug: a dry run says
"nothing was written, `tmp/upgrade/` included" and lists what is already there
as somebody else's plan, and a real run clears its own sidecars before writing
so what is there afterwards is this run and nothing else. Clearing is the only
deletion this tool performs, so it is bounded to the two suffixes it writes —
a file of the user's in that directory survives — and the count is reported
rather than silent.

`bin/skeletor-verify`'s `sidecar_gate` is what would have caught it, and it is
the first thing here to execute the conflict and collision branches at all:
every other upgrade gate runs against a fresh tree, where the answer is "already
current" and neither branch is reached. It manufactures the skew through
`--no-base`, which classifies from the recorded hashes alone — tamper one
recorded hash for a conflict, delete one entry for a collision — so it needs no
second checkout and no version skew to arrange. The prose assertion is by
**pattern**: a block naming the placeholder form `tmp/upgrade/<path>` is a
direction to open a file, and must be hypothetical under a dry run and
indicative under a real one. The bare directory in the footer and in the stale
listing is a statement about the run, not an instruction, and is out of scope by
construction rather than by allowlist. That predicate is on its second draft —
the first was per-line, and flagged the continuation line of a correct sentence,
because these sentences wrap and the tense sits on whichever line it fell on.

The **arguments** are the primary record; the `files` hashes are a fallback for
when the base render is out of reach — a `--depth 1` clone, a tarball, a
collected ref. They answer only "has anybody touched this file?", which is
enough to update the ~103 of 111 files that are machinery, and not enough to
merge, which needs the base *text*. `--no-base` takes that path deliberately and
answers "what have I edited?" without git at all.

The **dirty-scaffold warning can now be sized**, which is a different thing from
clearing it. A tree scaffolded from a dirty checkout records a `-dirty` ref; the
upgrade strips it, renders the base from the committed part, and warns that
uncommitted template edits will read as template changes now. That warning is
unconditional — it is printed before anything can know better — and proto.pilot
asked the right question of it: *is my conflict count partly an artefact, and
how much?* Unanswerable from their side, and answerable from here.

It is **not** permanent, which this file claimed for a while on the strength of
the one case that had been tested. The claim came from watching a refusal, where
nothing is written and so nothing clears, and generalising to every case.
proto.pilot measured a tree going `v0.2.0-dirty` → a clean tag across a single
upgrade and said so. Three outcomes: the edit touched a shipped file, so
`cross_check` refuses and the ref stays, correctly, because that base really is
unreproducible; the upgrade applies something, so the manifest is rewritten from
a render that exists in a commit and the ref is clean from then on; or the
upgrade applies nothing, and it returns next run. Only the first is permanent.

A `cross_check` pass settles it. That check is a bijection with equal hashes in
both directions, so it holds exactly when the base render reproduces what was
scaffolded, file for file: an uncommitted edit that changed a shipped file moves
a hash, one that added a file is recorded and unrendered, one that removed a
file is rendered and unrecorded. All three are refusals. What survives a pass is
an uncommitted edit to something the scaffold does not ship, which changes no
classification at all. So the run says so, and the warning above points forward
to that line. It is the only run that can: in the `--no-base` fallback the
hashes came from the dirty render and there is nothing to check them against.

Verified in both directions by planting the edit — inside `template/` it is a
manifest-drift refusal, outside it the bounding line prints.

That gate needs a **version gap** to cross, since the manifest is only rewritten
when the upgrade applies something, and it used to pick one by asking whether a
tag's `template/` differs from HEAD's. That is a broader question than the gate
needs and it went red on the first release that exercised the difference: a
docs-only commit touching one file in `template/governed/`, against a scaffold
at `core`, which correctly applied nothing. A true statement about the wrong
scenario — this repository's own recurring failure, arriving inside the gate for
a report about it, and only on CI, because a *dirty* checkout here happened to
supply a different gap. The scaffold is the fullest configuration now, so nearly
every template change is a shipped one, and each candidate tag is **tried** —
scaffold, upgrade, ask git what changed — until one applies something. The
difference between the two is that a selector this gate cannot satisfy is now a
failure that names every tag it tried, rather than an assertion about a scenario
that did not happen.

A hash is a derived value with a second home, which is normally the thing this
project refuses. It earns its place by being **checked against its source on
every ordinary run**: when the base is rendered it is re-hashed, and a manifest
that disagrees is a hard failure. A cache validated every time it is bypassed
cannot rot unnoticed. Note also what a match proves — an equal hash means the
file *is* byte-for-byte what skeletor generated, so replacing it cannot lose an
edit that was never made. That is why the fallback is allowed to write at all.

Two post-copy steps make "what skeletor produces" harder than it looks, and the
first consumer found the difference. `register_shipped_docs` and `regen.py` both
*read* the tree they write into, so in a `--force` scaffold they read the user's
files too: proto.pilot had a `docs/hosted.md`, that step correctly gave it a row
in `.github/DOCS_INDEX.md`, and the manifest then recorded a hash of a file no
render of those arguments can produce. Every later upgrade refused — this time on
a wrong hash rather than a surplus entry, which is the worse of the two, because
a surplus entry can be deleted by hand and a wrong one cannot. Recording it was
not a near miss either: in the offline fallback that file would read as "template
moved, user untouched" and be overwritten with a render that has no row for their
doc, silently losing the thing the step exists to add.

So on a populated target the post-copy steps run **twice** — once on the tree,
which is what the user wants, and once in `pristine_post_copy()` on a copy holding
only the rendered files, which at that instant is byte-for-byte the base render.
The second run is what the manifest records. It costs a file copy and one
subprocess, and is skipped entirely for an empty target, where the two trees are
the same by definition.

For a manifest already written by a version that got this wrong,
`bin/skeletor-upgrade --repair-manifest` re-derives the whole map from the base
render standing in front of it and stops without upgrading. It has to be a
re-derivation rather than an edit, because the correct value is a hash of a render
and only skeletor can produce that render. It refuses under `--no-base` for the
same reason.

The hashes recorded are of **what skeletor produces**, never of what is on disk.
The difference decides whether the next upgrade destroys work: a merged file is
neither the old render nor the new one, so hashing the tree would record it as
pristine and the following run would overwrite the merge.

**A file skeletor wrote and the user deleted is not put back.** That is the
fourth category, and it is what makes partial adoption survivable. `AGENTS.md`
calls a `--force` scaffold into a working repository *the usual case*, and every
partial adoption is a set of deletions — take the rules, keep your own CI, drop
Release Please. An absent file was classified purely on being absent, so every
one of those came back on the next upgrade, reported as a green "new file added"
and written without asking. Worse than a conflict, which at least stops: a
decision that has to be re-made on a schedule is not a decision.

The manifest already draws the line and needs no decline list: an entry means
skeletor *wrote* that file here, so its absence is a deletion; no entry means the
template has only just started shipping it, and adding it is what an upgrade is
for. Both directions are gated, because over-applying the fix would silently stop
delivering genuinely new files — the same wrong answer facing the other way. A
persisted list of declines would be a second home for a fact the filesystem
already states, and would go stale the moment somebody changed their mind by
restoring the file.

It reports as one standing line rather than a roll-call, because it is permanent:
the manifest is re-copied from the head render on every applying run, so a
decline persists and is reported forever. Only the subset the template has
*changed* since is itemised, with the current version in `tmp/upgrade/`, since
that is the only part there is anything new to decide about. sky.boss found this
while weighing a retrofit and asking whether settled declines would become
recurring conflicts; they would have become something quieter and worse.

A file the user had *before* the template claimed its path is reported as its own
category, not as an edit. The handling is identical — left alone, template's
version to `tmp/upgrade/`, never overwritten — and only the sentence differs,
because the sentence is what the reader acts on: "you edited this" sends somebody
to `git log` for a change they never made, when the real question is whether two
files written for the same purpose should now be one. The manifest draws that line
exactly, which is why it costs nothing: an entry with a different hash is an edit,
no entry at all is a collision. proto.pilot hit it on a test file it had written
by hand — the same one whose design this template then adopted, so the collision
was with its own idea arriving back as ours.

`skeletor-verify` runs `skeletor-upgrade --dry-run` against every fresh scaffold
twice — once `--from-dir .` and once `--no-base` — and requires "already
current" from both. The offline pass matters most: it is the path nobody runs by
hand, so it is the one that would rot, and a mismatch there is precisely when
the fallback would misclassify an edited file as untouched and overwrite it. That is the cheap test of the
manifest, and it fails on the thing that actually breaks: `--slug`, `--cli` and
`--env-prefix` all default from the *target directory name*, and an upgrade
renders into a temporary directory with a different one. A manifest that cannot
reproduce its own tree makes every later upgrade a diff against the wrong base
— which is worse than no upgrade, because it looks like it worked.

**`--versioning tag` is the one flag that changes what ships**, and it is a
*subtraction and nothing else* — the Release Please config and manifest,
`VERSION`, and the release-train skill, which is a state machine for a release
PR nobody will open. That shape is the rule, not a coincidence: the scaffold is
this repository's only test, so a mode that wrote files *differently* would need
a verification grid it cannot afford, and it would put a conditional into every
doc describing the workflow.

The question it answers is a fact about the project rather than a taste — **does
anything deploy this?** A published artifact needs a tracked `VERSION`, because
what a user runs has no `.git` and `git describe` there answers nothing. A
repository run from a checkout has the tag, and `VERSION` is then a second home
for a number `git describe` already knows, kept in step by a bot. skeletor itself
is the `tag` case, which is why there is no `VERSION` file here.

The verb matters and stash.flow supplied the correction: this said *install*,
which reads as packaging and invites the answer "we don't publish to PyPI, so
no". Their collector is a desktop build and their node ships as Compose —
nothing is installed in that sense and every one of those artifacts is a tree
with no git history. The flag reads as being about tagging discipline; the case
it actually turns on is distribution.

Two mechanisms make the subtraction safe, and both key on **the tree rather than
the flag** — the flag is gone by the time anything reads them:

- `drop_absent_prose` removes markdown blocks marked `<!-- SCAFFOLD-IF <path> -->`
  when that path is absent, and `SCAFFOLD-IF-NOT` is the inverse. The pair
  exists because subtraction alone leaves a lie behind: `tag` still *has* a
  release procedure — `git tag -a` — so a `## Releases` heading with nothing
  under it would be worse than the wrong paragraph. It ships the true half of
  each alternative, never a sentence hedged to be true in both. Markdown only,
  because `<!-- -->` is a syntax error in YAML; workflows ask the same question
  with a file test in the step, which is that language's spelling of it.
- Workflow steps guard on `[ -f .github/release-please-config.json ]`. The
  release job still runs and still *reports*, because a required context that
  never reports blocks a pull request forever — it simply has nothing to do.

Those two files name a path that may not exist, which is indistinguishable to a
path-checking gate from sending a reader somewhere that is not there. They say
which they are, at the site, with `SCAFFOLD-OPTIONAL <path>` — and the
tier-composition gate checks both staleness directions, so a declaration for a
path that ships everywhere, or one whose file stopped mentioning it, is red.
That is the only exemption mechanism the gate has, and it is two entries.

**Pins are reported, never bumped automatically.** `bin/skeletor-check-pins`
discovers every pinned version by pattern and asks the registries what is
current; `.github/workflows/pins.yml` puts the result in one issue, weekly.
Applying a report is a separate, deliberate act, because a bump changes what
`black` does to a generated tree and what a user's first `pre-commit run` does —
and only `bin/skeletor-verify` can judge that. Deliberate exceptions go in
`.github/pin-allowlist.yaml` with a reason.

The hazard that rule was written around now has a tool rather than a warning.
`pyright` is pinned in **three files under two ecosystem keys** — `npm:pyright`
for the pre-commit hook's `rev`, `pypi:pyright` for `scripts/requirements.txt`
and for `ci.yml`'s `pip install` — because they are looked up in different
registries, and `check-pins` is right to report them separately. Anybody working
down that report key by key bumps one and stops, producing a tree whose own
`test_lint_tool_parity.py` is red on arrival, which this repo treats as the one
unacceptable outcome. `black` has the same shape.

`bin/skeletor-bump <tool> <version>` takes the **tool name, not the pin key**,
rewrites every location every ecosystem resolves that name to, and has no way to
ask it for half. It reads its locations from `check-pins`' own `discover()`
rather than repeating the patterns — a second copy would bump the locations this
file knows about while the report kept naming the ones it knows about, both of
them green — and it re-runs that discovery afterwards, failing if any location
still holds the old version. It does not run the gates and does not decide
whether a bump is wanted; it prints `bin/skeletor-verify` as the next step,
because that is the step that makes a bump real.

The weekly pass this is the middle of — read the report, bump whole pins,
verify, PR, allowlist a refusal, tag what shipped — is written once, in
[`docs/MAINTENANCE.md`](docs/MAINTENANCE.md), so a person, a scheduled agent and
a workflow can run the same procedure instead of three copies of it.

---

## Architecture

### Overlay composition

`bin/skeletor-new` copies **overlay directories in order**, later ones
overwriting earlier ones, so a tier can specialise a file a lower tier ships:

```
core  →  governed  →  agentic          (cumulative tiers, TIERS map in skeletor-new)
                   +  python / node    (language overlay)
each of the above  +  agent-claude/<overlay>   (agent overlay, if it exists)
```

The **agent overlay is applied per overlay, not once at the end**, because its
files are tier-shaped: `.claude/skills/` describes the agentic workflow and has
no meaning at `core`. An agent overlay that does not exist is skipped — most
overlays ship no vendor files — while a missing *tier* overlay stays a hard
error, because that one is always a bug.

**Only tooling goes in an agent overlay**: settings, hooks, subagents, skills.
The conventions live in `docs/rules/`, are plain markdown, and are shipped
whatever `--agent` says. Nothing auto-loads them for any agent — they are read
because `AGENTS.md` names them — so a vendor-branded home would have been a
claim that was never true, and would have made the project's own testing and
commit rules look optional to anyone not using that tool. `--agent none` is
gated in `bin/skeletor-verify`: no `.claude/` anywhere, all seven rule files
present, and `check docs` still green.

Consequences to keep in mind when editing:

- A file in `template/agentic/` **replaces** the `core` copy wholesale. There is
  no merge. If a higher tier needs to add one row to a core file, prefer
  extending it at scaffold time (see `register_shipped_docs`) over duplicating
  the file — two copies of a table is precisely the drift this shell exists to
  prevent.
- `template/agentic/.env.example` exists **because** it must replace core's, to
  add the heartbeat variables that `tests/test_reporting_jobs.py` requires.

### Placeholder substitution

Every text file is rendered through `render()`, which substitutes `{{NAME}}`
tokens and **raises on an unknown one**. That strictness is deliberate: a typo'd
placeholder would otherwise ship literally into a user's repo.

The full set is defined in `substitutions()` in `bin/skeletor-new`. Adding a
placeholder means adding it there; adding a `{{FOO}}` to a template without it
fails the scaffold loudly, which is the intended behaviour.

Two special cases:

- `template/core/CLI_WRAPPER` is renamed to the project's `--cli` value during
  the copy. It cannot live in the template under its final name.
- Binary suffixes (`BINARY_SUFFIXES`) are copied byte-for-byte, and
  `__pycache__` is skipped — a stray `.pyc` in the template breaks the copy with
  a `UnicodeDecodeError`.

### Post-copy steps

After copying, the scaffolder does three things so the output is green
immediately: registers overlay-shipped docs into `.github/DOCS_INDEX.md`
(`register_shipped_docs`), generates the docs indexes (`scripts/docs/regen.py`),
and installs the `regen-docs` merge driver.

### What the generated project contains

The generated tree's own architecture is documented in the files it ships —
`docs/DEVELOPMENT.md`, `docs/CLI.md`, and `.claude/rules/*.md`. The pieces that
interlock, and which you cannot understand from one file:

- **The docs lifecycle.** `scripts/docs/plans.py` is the shared scanner; the two
  index generators and two README builders are thin wrappers over it.
  `queue_order.py` is imported by every consumer of the ready queue so the
  published order is the real one. `frontmatter.py` is a deliberately
  non-general parser for a schema we also generate.

  **Filing a plan strips the tank-only fields in both forms**, and the two halves
  live apart on purpose: `add_frontmatter.py` clears the frontmatter (it runs on
  every `docs index`, so it must not touch prose), while `cli/docs.py` removes
  the `> **Shelf-Status**:` header lines during the move — the one deliberate
  moment that knows the plan has left the tank. A header beats frontmatter by
  design, so neither half is sufficient. `plans.TANK_ONLY` owns the set;
  `test_docs_lifecycle.py` proves the strip end-to-end and
  `test_docs_pipeline.py` ratchets the archive at 0 for a hand-moved plan.
- **CLI command discovery.** `cli/__init__.py` discovers command groups by
  scanning the package — a module exporting a click Group named after itself is
  registered by existing. This is why the `governed` and `agentic` overlays can
  drop `commit.py`, `worktree.py` and `report.py` into `cli/` without patching
  any import list.
- **The job registry** (`agentic`). `scripts/reporting/jobs.py` is the single
  source for the crontab, the `report` subcommands and the status viewer;
  `cli/report.py` *generates* its subcommands from it, and
  `tests/test_reporting_jobs.py` asserts both directions plus the prompt files,
  heartbeat variables and cron-collision rules.
- **The dead-reference check and its clone depth.**
  `tests/test_docs_name_live_code.py` fails when a reference doc names a callable
  the tree once defined and no longer does — it asks git, so a name that was never
  the tree's own is out of scope by construction rather than by allowlist, and the
  narrative stages of the docs lifecycle are excluded by role, read from
  `scripts/paths.py`. It is a ratchet at 0: a one-commit scaffold cannot have
  removed anything. The interlock is `ci.yml`, whose unit job checks out with
  `fetch-depth: 0` **because of this test** — `git log --all` answers "never
  defined" for everything in a shallow clone, so the check would pass having
  looked at nothing. It asserts the clone is not shallow rather than trusting it,
  which turns that silent pass into a loud failure; the fetch depth is what makes
  it pass honestly instead.

---

## Invariants for editing templates

1. **Every rule carries its reason, in the file that states it.** A rule whose
   reason is written down can be evaluated when it becomes inconvenient; one
   without gets deleted by whoever trips over it. This applies to config files
   too — `.flake8`, `pytest.ini` and `jobs.py` all explain themselves.

2. **Never introduce a list where a pattern will do.** If a template needs a set
   of things checked, discover the set (any file with a marker, any job matching
   a pattern) and put exemptions in an allowlist with a written reason.
   Forgetting to update a registry is the bug most of this shell exists to
   prevent — do not add one.

   **An exemption is checked against the thing it exempts, on every run.** A
   reason makes an entry a decision record; nothing keeps the decision true. An
   entry whose file was fixed has outlived its reason, and one whose file left
   the tree is worse — the path can come back for something else and arrive
   pre-exempted, which is an exemption nobody chose. Both are stale, both fail,
   and a stale entry is deleted rather than re-justified. This is the manifest
   rule in another costume: a cache validated on every run that does not need it
   cannot rot unnoticed.

   **One reader, discovered coverage.** The tree ships four allowlists, and for
   a while they shipped four copies of the same parsing — which is how a shared
   format actually fails: each copy is right about the keys its own caller uses,
   and nothing compares them. `scripts/allowlist.py` owns the reading now.
   `bin/skeletor-verify`'s `allowlist_gate` owns the coverage, and it
   **discovers** `*_allowlist.yaml` rather than listing them, planting a
   meaningless entry in each and requiring the tree's own gates to go red. That
   gate exists because the first pass at this rule was itself a list: two
   allowlists got a staleness check because they were the two in front of me,
   and the two missed were the two nothing would have complained about. A grep
   for the word would not have helped either — the drift allowlist's docstring
   promised an escape hatch its reader could not parse.

   **A negative assertion over a set that could be empty is a tautology**, and
   a green negative looks identical whether the thing did not happen or nobody
   looked. This repository states that for pyright's `filesAnalyzed` and for the
   lint gates asserting they enumerated the tree, and had not applied it to two
   of the suites it ships: `test_marker_coverage.py` passed 2/2 and
   `test_state_paths.py` 5/5 with their enumerations forced empty. Neither is
   empty today — the hazard is a rename of `tests/` or `cli/` disarming them in
   silence, which is exactly what marker-based suites exist to prevent. Both now
   assert the scan found something, the convention `test_cli_smoke.py` and
   `test_docs_name_real_commands.py` already followed. Reported as a class by
   proto.pilot, who found a `monkeypatch` aimed at the module a call had left,
   turning a negative into a tautology with nothing in the output to say so.

   **The empty case can be legitimate and still be a defect**, which is the
   half this had not reached. `test_a_host_exemption_is_still_true` parametrized
   over the scripts declaring `CANNOT_RUN_ON_HOST`, and zero of them is the
   *expected* state of a fresh scaffold — the docstring said so, as though that
   settled it. pytest reports an empty parameter set by **skipping**, and
   `skip_budget.json` ships at 0, so every scaffold was born one skip over its
   own ratchet. An assertion that is correct when empty and a skip that is
   emitted when empty are different things, and a ratchet only sees the second.
   The fix is a loop rather than a parametrize, and what makes the empty case
   non-vacuous is not a guard beside it but the shape of the enumeration: the
   exempt and runnable sets partition the checkers, so an exemption this scanner
   fails to see lands in the other set and fails loudly there.

   It shipped because the ratchet that would have caught it **was not running**.
   `ci.yml` ran pytest with no `--junitxml`, and `check_skip_budget.py` answered
   a missing report with a warning and exit 0 — so the check that exists to
   catch a suite quietly stopping testing was itself quietly not testing, on
   every push, in every generated repository. stash.flow found both, by writing
   the report by hand and watching a green step turn red. Two bugs that hid each
   other, and the second is the general one: **there is no case where "I could
   not measure" is the same answer as "the budget is respected"**, so neither
   ratchet has a warn-and-pass path any more. `check_coverage_budget.py` had the
   identical hole, latent — its one workflow does write the report — which is
   the pair worth reading together, since a latent one is an edited workflow
   away from the live one.

   `bin/skeletor-verify` could not see it: it runs a tree's gates directly,
   where the hand invocation is fine, and the hole was in what the *workflow*
   passes. So the tree ships `tests/test_ci_ratchet_inputs.py`, which requires
   the artifact a ratchet reads to be named earlier in the same job — enrolment
   by pattern at both ends, since a ratchet is any `scripts/check_*.py` naming a
   file under `tmp/`. It reads the workflows with comments blanked, and the
   plant proves why: `# TODO: restore --junitxml=tmp/junit.xml here` leaves the
   string in the file and the job without the flag.

   Measured, not grepped: the heuristic that found these also produced two false
   positives, and it missed `test_the_scan_finds_the_docs` because its name says
   "finds" and the pattern said "found". The question that settles it is not
   *does a guard exist* but *does the suite still pass with the enumeration
   emptied* — which is the same plant-and-require-red the gates use.

   The guard is now the enumeration, not a companion beside it:
   `tests/scanning.py`'s `scanned(items, what, least=1)` refuses a scan too small
   to prove anything, and cannot be omitted without deleting the loop. That is
   proto.pilot's shape and their argument beats the helper — **a convention you
   must remember to apply is a registry with no enforcement**, which is what Rule
   2 is about. Their evidence: running this sweep on their tree found *seven*
   unguarded sites, one written the day before. `least` above 1 is the fixture
   rule made cheap to express — a filter tested against one item is unobservable,
   because "everything" and "the one match" are the same set — and it was already
   here as a hand-written `len(COMMANDS) >= 5` in exactly one place.

   **A plant that did not land is indistinguishable from a gate that works.**
   Both print green. proto.pilot lost an hour to a `sed` whose pattern silently
   matched nothing; the same afternoon here, a plant passed because the gate
   cloned committed state and the plant was uncommitted, and another passed
   because the value under test was computed at two call sites and the plant hit
   the one the gate did not read. So a plant asserts its target exists before
   writing, and a green result after planting is a claim about the plant first
   and the gate second.

   **The example you reach for first cannot discriminate.** Picking a fixture is
   picking the simplest one, and simple means fewest ways to be wrong — so the
   convenient case passes under the real fix and the plausible one alike.
   `declined_gate` took `sorted(manifest)[:2]`, the two most convenient files in
   the tree, and with them the "the template has changed since you declined it"
   branch could never fire: this gate scaffolds and upgrades from one HEAD, so
   every recorded hash equals the head render's by construction. That branch had
   report text written for it and nothing exercising it. jam.sense named the rule
   from the other side — of five labels their gate matches, the one anybody would
   reach for first is the only one with no prose mentions, so it is the only one
   that cannot tell a comment-masking fix from a docstring-masking one.

   **A detector is validated by finding the site, not the file.** Asserting that
   a check found *something* is the version of this rule this repository already
   held — pyright's `filesAnalyzed`, the lint gates asserting they enumerated the
   tree. It is necessary and it is not sufficient. jam.sense ran a naive grep for
   `worktree remove` against their tree and got two hits in the right file, both
   an error message and a docstring, while the call it was hunting — an argv list
   — went unseen. A clean miss announces itself; a lucky hit gets signed off.

   The corollary that cost the most here: **a check that greps source must mask
   comments, and the ones that scan for a requirement are the ones that forget.**
   `check_output_discipline.py` masks prose and `check_doc_links.py` blanks
   fences, because both hunt for a *mistake* and a false positive gets reported.
   `check_workflow_drift.py` and `test_ci_draft_gate.py` hunted for a
   *requirement*, matched raw text, and both passed while the thing they guard
   was absent — a job with no `actions/setup-python` but a TODO saying to add
   one, and a `ready_for_review` trigger deleted with a comment left behind. The
   string most likely to appear where the thing is missing is a comment saying it
   should be there, so the false pass is perfectly correlated with the defect.
   `scripts/yaml_text.py` is the one home for that masking.

   **The tell that a predicate is wrong is not the number of exemptions — it is
   what they are about.** This repository has stated the rule twice with two
   different numbers ("four things", "five things"), which is itself the
   evidence: the count was never the load-bearing part. Entries about *code the
   predicate mis-shaped* mean the predicate is wrong, and the fix is a tighter
   predicate rather than a longer list. Entries about *the convention's own
   vocabulary* — the sentence defining a notation, a dated record naming the old
   name deliberately — are a different animal, because the thing excluded is
   prose about the notation and no predicate over the notation can see out of
   it. sky.boss drew that line, from a doc-link gate whose two entries are both
   of the second kind and whose staleness assertion runs in both directions.

   Where a structural marker separates the two, prefer it to either:
   `test_docs_name_real_commands.py` faced exactly the vocabulary problem —
   prose legitimately names commands that do not exist, in three distinct ways —
   and scoping to fenced ```bash blocks removed all three at once, because a
   fence is the difference between describing a command and telling you to run
   it. Zero exemptions, measured on a real tree.

3. **Fields that are guessed wrong must not be inferred.** `blocked_on`,
   `queue_order` and `review_pr` are read only from explicit lines. A malformed
   value sorts last rather than raising or silently winning.

4. **A generated artifact is never hand-editable**, and its generator emits a
   `<!-- GENERATED by ... -->` banner plus a stable field order, so a
   regeneration that changed nothing produces no diff.

5. **A gate a scaffold cannot pass does not ship.** If you add a check, either
   the shipped tree satisfies it or the scaffolder makes it satisfied.

6. **Ratchets ship at 0 for a greenfield tree** and document how to baseline
   them for an adoption. Never ship a ratchet that is red on arrival.

7. **Template prose is read in the reader's tree, and must be true there.** The
   generator is absent by then, and so is this repository. Two ways a sentence
   fails that test, both of which shipped:

   **A guarantee implemented by rendering cannot survive rendering.**
   `docs/DEVELOPMENT.md` said its setup block "is rendered from
   `setup_commands()` in the scaffolder — the same source as the README's — so
   there is exactly one place these steps are written down". Every word was true
   here and none of it in a scaffold, where the two blocks are static text that
   nothing compares. The tell is narrower than tense: **a sentence in the present
   tense about an ongoing guarantee that was actually a one-time act** — `is
   rendered from`, `stays in sync with`, `the scaffolder installs it`. Standing
   conventions in `docs/rules/` are present-tense and fine; a *mechanism* named
   as currently operating is the dangerous subset, and the reader cannot check it
   because the generator is a repository they may not have. The merge-driver
   bullet was the same sentence at its worst: it described the untracked-`.git/config`
   hazard from the one machine where that hazard cannot occur, so it read
   "the scaffolder installs it" to every clone after the first, which is precisely
   the population it was written for.

   **A count measured in one tier, written into a file every tier carries.**
   `scripts/yaml_text.py` said "two of the four workflows this template ships";
   `core` ships three and `governed` adds the fourth. Same failure with the axis
   changed from time to space, same remedy — state the shape, not the number.

   Both were found by stash.flow, from an adopted tree, which is where they are
   visible and here is where they are not.

---

## Conventions in this repo

- Conventional commits (`feat`/`fix`/`docs`/`chore`/`refactor`/`ci`/`test`), one
  subject line.
- `docs:` for changes under `docs/` only.
- Template content is prose as much as code — match the surrounding voice:
  specific, causal, and willing to say what went wrong.

**Versioning.** skeletor is versioned by annotated git tag and nothing else.
There is deliberately **no `VERSION` file**: nothing installs this repository, so
a file would be a second home for a number whose first home is the tag — the
copy this project refuses everywhere else.

The tag is not decoration. `skeletor_ref()` writes `git describe --tags --always
--dirty` into every scaffold's `.skeletor.json`, and that is the value
`bin/skeletor-upgrade` re-renders a tree's base from. Untagged, it recorded a
bare sha: unreadable, and strippable by a rebase, which drops an upgrade into the
degraded hash-only fallback that can classify but cannot merge. Tagged, a
scaffold records `v0.1.0` or `v0.1.0-3-gabc1234`.

So: tag after a change users would scaffold against, `git tag -a vX.Y.Z` with a
message saying what moved, and push the tag — an unpushed tag describes a base
only this machine can resolve.
