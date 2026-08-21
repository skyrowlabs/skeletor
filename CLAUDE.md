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

# Full option set
bin/skeletor-new --help

# Verify a template change end-to-end — do this after ANY edit under template/
bin/skeletor-new /tmp/probe --name Probe --cli probe --tier agentic --tagline x --force
cd /tmp/probe
python -m venv .venv && .venv/bin/pip install -q pytest click
.venv/bin/python -m pytest tests/ -m unit -q     # must be green
./probe check docs                                # must be 5/5 green
./probe --help                                    # every group must register
```

There is no test suite for skeletor itself. **The scaffold IS the test**: a
template change is verified by generating a tree and running that tree's own
gates. A scaffold whose first check is red teaches the user that red is normal,
so "a fresh tree passes its own gates" is the definition of done here.

Verify all three tiers when a change touches `template/core/`, since `governed`
and `agentic` compose on top of it:

```bash
for t in core governed agentic; do
  bin/skeletor-new /tmp/probe-$t --name P --cli p --tier $t --tagline x --force
done
```

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
