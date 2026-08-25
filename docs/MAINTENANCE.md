# Maintaining skeletor

The weekly pass, written so a person, a scheduled agent or a workflow can all
run the same one. There is deliberately one copy of it: the last thing this
repository learned the hard way is that a procedure kept in two places drifts,
and the wrong copy is the one being read.

---

## What already runs without anybody

| | When | Produces |
| --- | --- | --- |
| `.github/workflows/verify.yml` | every push to `main`, every PR, Mondays 06:17 UTC | `bin/skeletor-verify` — every tier scaffolded and gated |
| `.github/workflows/pins.yml` | Mondays 06:23 UTC | **one** issue titled *Template pin freshness*, updated in place |

Neither changes a file. `verify.yml` answers "is what we ship still green"; the
pins report answers "how far behind are the versions we start other people's
repositories on". That second question has no other way of being asked — there
is no lockfile here to nag anybody, and a stale pin is invisible from inside
this repo while being inherited by every project scaffolded after it went stale.

The pins job reports into a single issue on purpose. A bot that opens a fresh
issue every week is a bot people mute, and a muted report is the same as no
report at all.

---

## The weekly pass

### 1. Read the report

Open the *Template pin freshness* issue, or run it locally:

```bash
bin/skeletor-check-pins            # human table
bin/skeletor-check-pins --json     # every finding, with every location
```

Four statuses. `current` needs nothing. `allowlisted` is a decision somebody
already made and wrote down in `.github/pin-allowlist.yaml` — read the reason
before disturbing it. `unknown` means the registry lookup failed, which is a
network problem and not a finding. `behind` and `disagrees` are the work.

`disagrees` is the more urgent of the two: it means one tool is pinned to two
different versions in two files, and the copy that is wrong is the one nobody is
reading.

### 2. Bump the whole pin, never a location

```bash
bin/skeletor-bump pyright 1.1.413 --dry-run   # see every location first
bin/skeletor-bump pyright 1.1.413
```

**Take the tool name, not the pin key.** `pyright` is pinned in three files
under two ecosystem keys — `npm:pyright` for the pre-commit hook's `rev`,
`pypi:pyright` for `scripts/requirements.txt` and for the `pip install` in
`ci.yml` — because they are looked up in different registries. Anybody working
down the report key by key bumps one and stops, and the result is a generated
tree whose own `tests/test_lint_tool_parity.py` is red on arrival. That is the
one outcome this repository treats as unacceptable, and `bin/skeletor-bump`
exists so there is no way to ask for half. It re-reads `check-pins`' own
discovery afterwards and fails if any location still holds the old version.

`black` has the same shape: `github:psf/black` plus `pypi:black`.

### 3. Verify, and believe only this

```bash
bin/skeletor-verify
```

Nothing before this step judged whether the bump is a good idea. A `black` bump
changes how a generated tree is formatted; a `pyright` bump changes what type
errors a fresh scaffold ships with; a hook `rev` bump changes what a user's first
`pre-commit run --all-files` does. Only a full scaffold-and-gate run can answer
that, which is why the bump tool prints this command instead of running it.

**Green:** commit each tool's bump on its own, `chore: bump <tool> to <version>`,
and open a PR. **Red:** stop. Do not patch the template to accommodate the new
version in the same change — revert the bump, open an issue with the failure
output, and let the two decisions be made separately. A bump that drags a
template fix along with it is a bump nobody can revert.

### 4. When the answer is "not yet"

Some pins should not be taken. Record the decision where the next reader will
trip over it, in `.github/pin-allowlist.yaml`:

```yaml
<ecosystem>:<name>: why, concretely, and what would change the answer
```

An allowlisted pin still appears in the report, marked as a decision rather than
as work. **Never allowlist a pin to make a report quiet** — that converts a
finding into a lie, and the reason it exists is that the reason has to survive
the person who made it.

### 5. Tag if anything shipped

If a merged change alters what a user would scaffold, cut a tag:

```bash
git tag -a vX.Y.Z -m "what moved, and why somebody would want it"
git push origin vX.Y.Z
```

`skeletor_ref()` writes `git describe` into every scaffold's `.skeletor.json`,
and that value is the base `bin/skeletor-upgrade` re-renders from. An untagged
run records a bare sha; an unpushed tag records a base only one machine can
resolve. See CLAUDE.md § Conventions.

---

## What an agent running this must not do

These are the failure modes, not a style guide. Each one has produced a bad
outcome in this repository or in the project it was extracted from.

- **Never merge on green.** The gates say the tree is consistent, not that the
  bump was wanted. A human merges.
- **Never bump a pin partially**, which means never edit a pinned version by
  hand when `bin/skeletor-bump` covers it.
- **Never make a red gate pass by weakening it.** If `bin/skeletor-verify` is
  red, the bump is the thing that is wrong, until somebody decides otherwise.
- **Never allowlist to silence.** See step 4.
- **Never open more than one issue for a recurring report.** Update in place, as
  `pins.yml` does.
- **Report the failure output, not a summary of it.** The point of a scheduled
  run is that nobody was watching; a paraphrase is the part that cannot be
  checked afterwards.

---

## Scheduling it

The procedure above is the whole job and does not care what invokes it. The
runner is a separate decision — a scheduled cloud agent, a workflow calling an
agent action, or a person on a Monday — and whichever it is, it should be
pointed at **this file** rather than given its own copy of these steps.
