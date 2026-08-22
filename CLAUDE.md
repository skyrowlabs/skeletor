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

The skill's source is `.claude/skills/new-project/SKILL.md`; `bin/skeletor-install-skill`
copies it to `~/.claude/skills/` and **rewrites the hard-coded skeletor path** to
wherever this checkout actually lives. If you change the skill, say so — the
installed copy does not update itself.

`AGENTS.md` and the skill are two renderings of one procedure. **Keep them in
sync**, or delete one. Two copies of a procedure drift, and the copy that is
wrong is the one being read — which is the rule this entire repository is an
application of.

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
bin/skeletor-new --help

# Verify a template change end-to-end — run this after ANY edit under template/
bin/skeletor-verify                    # every tier x every language
bin/skeletor-verify --tier core --keep # one tier, trees left behind to inspect

# How far behind are the versions we start other people's repos on?
bin/skeletor-check-pins
```

There is no test suite for skeletor itself. **The scaffold IS the test**: a
template change is verified by generating a tree and running that tree's own
gates. A scaffold whose first check is red teaches the user that red is normal,
so "a fresh tree passes its own gates" is the definition of done here.

`bin/skeletor-verify` is that procedure, executable. It generates every tier
against every language — a placeholder that only appears in the `node` overlay
is a `render()` failure a user would otherwise find first — and against each
Python tree runs the unit suite, `check docs`, `check merge-drivers`, a
`--help` group-registration check, a static check that every `script()` call in
the tree's CLI names a file that exists, and the lint hooks. eslint and prettier
run once, on the fullest tier's `both` tree, and the fullest tier is scaffolded
a second time into a deliberately long path.

Those last two are each a bug that shipped. `script()` joins its argument onto
`PROJECT_ROOT`, so `script("-m", "pytest", ...)` became the path `<root>/-m` and
made `check pre-push` — the first command the scaffolder tells a user to run —
impossible to pass at any tier; `module()` now exists so a flag has its own
door. And the long path exists because `black` rewrites an over-long string
assignment only when the parenthesised form would fit, so an absolute path baked
into a source line is red for one band of checkout depths and green either side
of it: the length there is derived from the tree's own line limit rather than
picked, and a round 120 sat past the band and caught nothing.

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

`pyright` is the one hook not gated here: it is a node package wearing a Python
name, and installing a JS toolchain to check types on a tree that has none is
not worth the minute. `{{CLI}} check lint` runs it in a real project.

Know what that costs. Two `reportAssignmentType` errors in `governed`'s
`cli/commit.py` shipped and stayed shipped, red in every scaffold at that tier
and above, while this file stayed green — the gap is real, and the compensating
control is that `AGENTS.md` and the skill both run `check pre-push` (which does
run pyright) before anything else, and stop if it is red.

Always run all tiers when a change touches `template/core/`, since `governed`
and `agentic` compose on top of it. That is the default; `--tier` is for
narrowing a debug loop, not for a final check.

**Pins are reported, never bumped automatically.** `bin/skeletor-check-pins`
discovers every pinned version by pattern and asks the registries what is
current; `.github/workflows/pins.yml` puts the result in one issue, weekly.
Bumping is a hand edit followed by `bin/skeletor-verify`, because a bump changes
what `black` does to a generated tree, and because `pyright` is pinned in three
places — a bot that bumps one of them produces a tree whose own
`test_lint_tool_parity.py` is red on arrival, which this repo treats as the one
unacceptable outcome. Deliberate exceptions go in `.github/pin-allowlist.yaml`
with a reason.

---

## Architecture

### Overlay composition

`bin/skeletor-new` copies **overlay directories in order**, later ones
overwriting earlier ones, so a tier can specialise a file a lower tier ships:

```
core  →  governed  →  agentic     (cumulative tiers, TIERS map in skeletor-new)
                   +  python / node   (language overlay, applied last)
```

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
