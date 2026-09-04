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
its own repository at its first commit, the lint hooks, pyright, and
`actionlint` over the workflows the tree ships.
eslint and prettier run once, on the fullest tier's `both` tree, and the fullest
tier is scaffolded a second time into a deliberately long path and a third time
into a directory that already has files in it.

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

The **arguments** are the primary record; the `files` hashes are a fallback for
when the base render is out of reach — a `--depth 1` clone, a tarball, a
collected ref. They answer only "has anybody touched this file?", which is
enough to update the ~103 of 111 files that are machinery, and not enough to
merge, which needs the base *text*. `--no-base` takes that path deliberately and
answers "what have I edited?" without git at all.

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
