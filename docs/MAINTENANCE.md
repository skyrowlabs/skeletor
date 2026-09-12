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

**`unknown` is not a finding and it is not a pass either.** `--fail-on-stale`
deliberately does not go red on it: an unreachable registry is no evidence of
staleness, and a gate that fails on a network blip is one people learn to
ignore. But that pin has not been checked, so `bin/skeletor-maintain` says so
rather than folding it into *every pin is current or allowlisted* — the summary
names the questions it answered, never the ones it asked.

`disagrees` is the more urgent of the two: it means one tool is pinned to two
different versions in two files, and the copy that is wrong is the one nobody is
reading.

### 1b. Read what moved upstream

`bin/skeletor-maintain` asks a third cheap question, and it is the only one that
looks outside this repository:

```bash
bin/skeletor-maintain              # includes the "from upstream" section
```

skeletor was **extracted from a mature production repository, and that
repository kept going.** So "am I current" has a second meaning here that no
gate in this tree can answer, because the answer lives in a checkout this one
does not contain.

**Two files, one job each.** `upstream.json` is tracked and public: the record
of what was taken, what was declined, and why. `upstream.local.json` is
gitignored and is yours: which repositories you watch, where they are
(`search_root`, if they are not beside this checkout), and how far each has been
read. A fresh clone has no local file and the report says so rather than naming
a repository you cannot open — write one to start watching anything.

**Being per-machine is the cost of that split, and the report carries it.** A
second checkout of skeletor has no `upstream.local.json` and therefore watches
nothing, which is correct and is not silent: the run prints a `⚠️` naming the
file to write, and the green line drops the upstream clause entirely. It used to
keep it, so a checkout watching nothing reported *nothing has moved in a
harvested path upstream* — the reassuring answer to a question it had never
asked.

The report names only the paths that have been harvested before *and* have moved
since the watermark, plus a count of everything else. That split is deliberate —
the harvested paths are the ones with a decision behind them, and burying four
of those under every commit an upstream made this week is how a report stops
being read.

**It reports and never adopts**, for the same reason step 2 bumps a pin and this
tool does not. Which of an upstream's changes generalises is a judgment every
time: most of what moves there is that product's own work, and the fraction that
is a reusable mechanism is decided by reading it.

When you have read a diff, record the decision **either way**:

* advance `read_through` to the commit you read to, and
* add what you took to that upstream's `sources`, with why it was worth taking,
* or add a `_not_taken` entry naming what you looked at and declined.

The `_not_taken` half is the one that pays. Without it the next pass re-reads
the same 2500-line module and re-reaches the same conclusion, and a decision
that has to be re-made on a schedule is not a decision.

The checkout is located **by its origin URL, never by a recorded path**, and a
linked worktree is skipped. Every worktree of a repository reports the same
`origin`, so the first alphabetical match is whichever one happens to sort
first — sitting on some feature branch. The first run of this found a
dependency-bump worktree and reported 11 commits of a Dependabot branch as
upstream movement.

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

**And say what green means, because for a formatter it means less than it
reads.** The grid scaffolds fresh trees, so the only source it can format is the
template's own — and a formatter release is interesting for exactly the
constructs the template does not contain. sky.boss took `isort 8.0.1 → 9.0.1`
here (`e246e7f`, whose message says the grid ran isort against every tier with
nothing to reformat) and hit the behaviour change immediately, in
`typings/rich_click/__init__.pyi`: 9.0.1 sorts a star import ahead of `X as X`
re-export aliases where 8.0.1 sorted it after. No scaffold has a `typings/`
directory or a single `.pyi` file, so the population the grid measured contained
none of the subject.

Their sentence, and it is this repository's own rule pointed at its own release
procedure: **a formatter bump can only break source the grid does not contain,
so a green grid is close to no evidence for it.** Green still means the template
is self-consistent under the new pin, which is worth having and is all it is.
Write the bump commit to claim that and no more, and expect the adopter's tree
to be where the real answer comes from.

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

**Tag before carrying a change into anybody's tree, not after.** An applying
`bin/skeletor-upgrade` is **refused** from a checkout sitting past its last tag,
because the stamp would be `vX.Y.Z-1-gabc1234` — a version nobody chose, and one
that sticks: the manifest is re-copied only by a run that applies something, so a
tree brought current keeps it indefinitely. Three adopter trees recorded one and
none could correct it from their side.

The remedy is the order above — tag, push, then upgrade. If you genuinely need to
hand over an untagged render, `--ref <some-tag>` pins the stamp and
`--allow-untagged` records the description anyway; both are deliberate, and
neither is the normal path.

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

`bin/skeletor-maintain` is this pass with the deterministic half already done. It
asks the questions no model is needed for — the ones numbered in its own module
docstring, which is where the list is kept rather than here — and only if one of
them is a problem does it wake an agent. On the roughly fifty weeks a year when
the answer is "nothing", a run costs one API call, one registry sweep and one
`git rev-list`.

**Two of those questions can fail to be answered**, and neither counts as work:
a CI verdict nobody could read, and a registry nobody could reach. Each prints a
`⚠️` and drops its clause from the green line. Exit 0 with a warning above it
means *nothing to do that I could see*, which is a different claim from *nothing
to do*.

```bash
bin/skeletor-maintain              # report; exit 1 if there is work
bin/skeletor-maintain --agent      # ... and hand that work to `claude`
bin/skeletor-maintain --agent --dry-run
```

It refuses to run on a dirty tree or off `main`. An unattended pass that starts
from uncommitted local edits cannot tell them from its own, and the first thing
it would do is commit somebody's work in progress.

### Weekly, on this machine

A systemd **user** timer. No root, no secret anywhere, and nothing about the
repository has to change.

`~/.config/systemd/user/skeletor-maintain.service`

```ini
[Unit]
Description=skeletor weekly maintenance pass

[Service]
Type=oneshot
# Both paths are your checkout. This file does not name one, for the same reason
# AGENTS.md does not: a path in prose is wrong for every checkout but one.
WorkingDirectory=/path/to/skeletor
ExecStart=/path/to/skeletor/bin/skeletor-maintain --agent
```

`~/.config/systemd/user/skeletor-maintain.timer`

```ini
[Unit]
Description=skeletor weekly maintenance pass

[Timer]
# After pins.yml has posted its issue (Mondays 06:23 UTC), and deliberately not
# on the hour or the half hour.
OnCalendar=Mon *-*-* 08:47:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now skeletor-maintain.timer
systemctl --user list-timers skeletor-maintain.timer      # when it next fires
journalctl --user -u skeletor-maintain.service -n 100     # what it did
```

`Persistent=true` is the line that makes a timer on a laptop worth having: if the
machine was asleep on Monday morning the run fires at the next boot rather than
being skipped until the following week. Add `loginctl enable-linger $USER` if it
should fire while you are not logged in.

The journal is the record. That is why `--agent` inherits stdio instead of
capturing it — a transcript printed after the fact is one nobody reads at the
moment it would have mattered.

### The two alternatives, and what they cost

**A workflow calling an agent action** puts the schedule next to `pins.yml` and
`verify.yml`, under the same review as any other change. It needs an
`ANTHROPIC_API_KEY` repository secret before it can run at all, which is a
credential living in the repo's settings rather than on one machine.

**A scheduled cloud agent** needs no secret in the repo and runs whether or not
any machine is on, but the schedule then lives outside the repository — it is
not version-controlled alongside the procedure it runs, and nothing here can
tell you it stopped firing.

Whichever runs it, point it at **this file** rather than giving it a copy of
these steps. One procedure.
