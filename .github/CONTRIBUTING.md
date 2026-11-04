# Contributing

## The short version

```bash
git switch -c fix/<slug> main
# ...work...
./skel check pre-push
git commit                       # conventional; the hook enforces it
gh pr create --draft --base main
# ...iterate in draft; a draft carrying code skips the expensive jobs...
gh pr ready <n>                  # once, when you believe it is green
```

## Branches

| Branch                | Role                                                  |
| --------------------- | ----------------------------------------------------- |
| `main`     | Integration. Cut branches from it; PRs target it.     |
| `main`  | Release. Versioned by annotated tag (`git tag -a`). Never commit direct. |

Force-push is fine on your own unreviewed branch — squashing your own in-flight
work is how four CI runs become one. Never on either branch above.

## Commits

One logical idea per commit, all of its files bundled in. One subject line.
See [`docs/rules/commits.md`](../docs/rules/commits.md); the commit-msg
hook enforces the format.

## Why drafts

A `synchronize` event on a **ready** PR re-runs everything that PR earns. Open
as a draft, push freely, flip to ready once. A draft carrying code still runs
the cheap jobs; what it skips is the expensive ones, and
[`.github/scripts/docs-only.cjs`](scripts/docs-only.cjs) is where that is
decided. Nothing is un-gated by this — GitHub blocks merging a draft, and
`ready_for_review` re-runs whatever the PR earns. **What it earns does not change
by leaving draft unless the base branch changes what it earns**: a code change
entering `main` earns the full set, and in a two-branch tree a code
change entering `main` earns the same jobs ready as it did in draft.
The full set still runs before anything is released — the merge is a push, and a
push earns everything.

## Docs are part of the change

Decide in planning which docs a change invalidates, and update them in the same
PR. A finished plan **moves** from `docs/TODO/` to `docs/implementations/` —
`skel docs file <slug> --category <category>` does the move and every
regeneration. Then `skel check doc-refs` and `skel check doc-links`:
**repoint, never delete.**
