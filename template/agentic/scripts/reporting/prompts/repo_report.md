# Repository Report

You are writing `docs/reports/regular/repository-report.md` for the **current
release window**.

## The window

Get it from `{{CLI}} docs release-window`. **Never** re-derive it, and never write
"since this last ran" — a window that straddles a release boundary cannot answer
the only question that matters about a finding: *is this in production now?*

Re-stamp only your own report:

```bash
python scripts/docs/release_window.py --apply --only repository-report.md
```

A bare `--apply` re-stamps every anchored report and dirties all of them.

## What to write

Sections, in this order. Each must be **falsifiable**: a claim a reader can check
against the repo, not a mood.

1. **Metrics** — from the collected data. Never hand-count; if a figure is not
   in the data, say so rather than estimating.
2. **What changed** — grouped by subsystem, with the commits that did it.
3. **Risks** — what is more likely to break than it was last window, and why.
4. **What is unfinished** — from the holding tank, in queue order.

## What not to write

- No praise, no summary of your own process, no "the codebase is in good shape".
- No finding without a location. `path:line` or it does not go in.
- No figure you did not receive in the collected data.
- If nothing meaningful changed, **say that in one line**. A report padded to
  look substantial is one nobody reads next week either.

## Finish

1. Write the report.
2. Re-stamp it (`--only`, above).
3. Commit: `docs(reports): refresh the repository report for <window>`.
