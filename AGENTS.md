# Agent Instructions — Set Up a New Project With skeletor

You have been asked to set up a project using skeletor. **This is a generator,
not a guide**: you run one command that copies real files. Do not hand-write the
scaffold.

skeletor lives at `~/skyrow.labs/skeletor`. Everything below assumes you are
standing in the **target** repository (usually empty).

---

## Step 1 — Ask the user five things

Ask all five in one go. Do not infer them; a wrong CLI name or base branch is
annoying to change later.

| Ask                | Default   | Note                                                    |
| ------------------ | --------- | -------------------------------------------------------- |
| **Tier**           | `core`    | The only real decision — see the table below             |
| Project name       | —         | Human form, e.g. "Order Service"                         |
| CLI name           | from slug | Becomes `./<name>`; short, lowercase                     |
| Tagline            | —         | One line: what the project is                            |
| Language           | `python`  | `python`, `node`, `both`, or `none`                      |

Defaults you only need to raise if the user has an opinion: base branch
`develop`, release branch `main`, Python `3.12`, line length `120`.

**Tiers** (cumulative — read `~/skyrow.labs/skeletor/docs/TIERS.md` for detail):

| Tier       | Take it when                                                     |
| ---------- | ----------------------------------------------------------------- |
| `core`     | Always. Agent rules, docs lifecycle, CLI, tests, CI gate, versioning |
| `governed` | A second person or agent touches the repo, or CI costs money      |
| `agentic`  | Things rot on their own — deps, docs, backlog — and nobody looks   |

Say plainly that an unmaintained gate is worse than an absent one, and let them
choose. Do not upsell `agentic` to a project that does not exist yet.

For `--tier agentic`, also ask the **timezone** the crontab will fire in. Never
leave it implicit.

---

## Step 2 — Generate

```bash
~/skyrow.labs/skeletor/bin/skeletor-new . --force --no-git \
  --name "Order Service" \
  --cli ord \
  --tagline "Takes orders, bills them, ships them." \
  --tier core \
  --language python
```

Use `--force --no-git` when scaffolding **into** the current repo (the usual
case). Drop both when creating a new directory:
`skeletor-new ../new-dir --name ...`.

Add `--org <github-org>` if you know it, and `--timezone <tz>` for the agentic
tier. Full flags: `skeletor-new --help`.

---

## Step 3 — Verify before doing anything else

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
./<cli> --help          # every command group registers
./<cli> check docs      # must be 5/5 green
./<cli> test unit       # must be green
```

If any of these is red, **stop and report it** — do not proceed and do not
"fix it up". A scaffold whose first check is red is a bug in skeletor, and it
teaches the user that red is normal.

Then install the hooks:

```bash
pre-commit install --install-hooks
python scripts/git/install_merge_drivers.py
```

---

## Step 4 — Fill in the SCAFFOLD markers

```bash
grep -rn "SCAFFOLD" --include='*.md' --include='*.yml' --include='*.py' .
```

These are the parts only this project's author can write. The two that matter
most, and which you should draft **with** the user rather than for them:

- **`CLAUDE.md` § Services** — the real components, ports, what each is for.
- **`CLAUDE.md` § Critical Rules** — the shipped rules are placeholders. Replace
  them with rules true of *this* project. Each rule must (a) state what goes
  wrong without it, concretely, and (b) be enforced by something, or be marked
  advisory. A rule with neither is decoration, and the first person under time
  pressure deletes it.

Leave the rest as markers if the project is too young to answer them; say which
you left.

---

## Step 5 — First commit

```bash
git add -A
git commit -m "chore: scaffold the project shell"
```

Conventional commits are enforced by the hook you just installed. One subject
line.

---

## Then hand off

Tell the user, in a few lines:

- Which tier you used and what that means they now have.
- Which SCAFFOLD markers are still open.
- The three commands they will use most: `./<cli> check pre-push`,
  `./<cli> test unit`, `./<cli> docs status`.
- That `docs/SETUP_GUIDE.md` in the new repo's source (`~/skyrow.labs/skeletor`)
  covers branch protection, the first plan, ratchet baselines, and the PR loop —
  steps 4 through 8 — which are worth doing but are not part of scaffolding.

---

## Adopting into an existing, non-empty repo

Different job, different risks. Read
`~/skyrow.labs/skeletor/docs/SETUP_GUIDE.md` § "Adopting this into an existing
repository" and follow it — in particular, **baseline every ratchet at what the
repo already has**, never at zero. A ratchet that starts red gets switched off,
and then the adoption has made things worse.
