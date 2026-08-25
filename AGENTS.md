# Agent Instructions — Set Up a New Project With skeletor

You have been asked to set up a project using skeletor. **This is a generator,
not a guide**: you run one command that copies real files. Do not hand-write the
scaffold.

skeletor is the directory this file is in; everything below writes it
`$SKELETOR`, and you already know what it is — you just read this from it. It is
not written down anywhere on purpose: a path in prose is wrong for every
checkout but the one it was authored on. Everything below assumes you are
standing in the **target** repository (usually empty), not in skeletor.

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

**Tiers** (cumulative — read `$SKELETOR/docs/TIERS.md` for detail):

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
$SKELETOR/bin/skeletor-new . --force \
  --name "Order Service" \
  --cli ord \
  --tagline "Takes orders, bills them, ships them." \
  --tier core \
  --language python
```

Use `--force` when scaffolding **into** the current directory (the usual
case); drop it when creating a new one: `skeletor-new ../new-dir --name ...`.

Do **not** add `--no-git`. It reads like the safe choice for an existing repo,
but a tree that already has a `.git` is skipped regardless — so the flag does
nothing in the case it looks written for, and in an empty directory it leaves a
tree with no repository: no first commit for `git diff` and `check reports` to
work against, and no `regen-docs` merge driver, whose definition lives in
`.git/config`.

Add `--org <github-org>` if you know it, and `--timezone <tz>` for the agentic
tier. Full flags: `skeletor-new --help`.

---

## Step 3 — Verify before doing anything else

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
npm install             # node/both trees only — eslint is a blocking gate
./<cli> --help          # every command group registers
./<cli> check pre-push  # lint + docs + unit tests, all of it
```

`check pre-push`, not `check docs` and `test unit` separately: those two skip
the lint gate, which is how a scaffold once shipped with `black`, `pyright` and
`eslint` red and nobody noticed for as long as the verification step never ran
them.

If any of it is red, **stop and report it** — do not proceed and do not "fix it
up". A scaffold whose first check is red is a bug in skeletor, and it teaches
the user that red is normal.

Then install the hooks:

```bash
.venv/bin/pre-commit install --install-hooks
.venv/bin/python scripts/git/install_merge_drivers.py
```

Every tool here is run by path, including the ones above. Nothing activates the
venv, so a bare `pre-commit` is not on PATH at all, and a bare `pip` resolves to
a system Python that on Arch, Debian 12+, Ubuntu 23.04+, Fedora or Homebrew
macOS refuses to install into itself (PEP 668).

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

## Step 5 — Commit your edits

```bash
git add -A
git commit -m "docs: fill in the scaffold markers"
```

The shell's own commit already exists — `skeletor-new` made it, which is what
gives `git diff` and `check reports` a HEAD to work against from the start, so
`git log` shows it before you write anything. This commit carries your Step 4
edits, not the scaffold. If you scaffolded into a repository that already had
history, the scaffolder committed nothing and this is the first commit after
all — read `git log` rather than assuming either.

Conventional commits are enforced by the hook you just installed. One subject
line.

---

## Then hand off

Tell the user, in a few lines:

- Which tier you used and what that means they now have.
- Which SCAFFOLD markers are still open.
- The three commands they will use most: `./<cli> check pre-push`,
  `./<cli> test unit`, `./<cli> docs status`.
- That `$SKELETOR/docs/SETUP_GUIDE.md` in the new repo's source covers
  branch protection, the first plan, ratchet baselines, and the PR loop —
  steps 4 through 8 — which are worth doing but are not part of scaffolding.

---

## Adopting into an existing, non-empty repo

Different job, different risks. Read
`$SKELETOR/docs/SETUP_GUIDE.md` § "Adopting this into an existing
repository" and follow it — in particular, **baseline every ratchet at what the
repo already has**, never at zero. A ratchet that starts red gets switched off,
and then the adoption has made things worse.
