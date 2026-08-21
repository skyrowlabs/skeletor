---
name: implement
description: Execute (or first write, then execute) a docs/TODO implementation plan end-to-end. Orchestrates the implementer, tester and documenter subagents from the main session, then files the completed plan to docs/implementations/. Use when the user says "implement docs/TODO/X.md", "work through the plan for X", or "plan and implement X".
---

# /implement — Plan Orchestrator

You are in the **main conversation**, so you CAN spawn subagents. Subagents
cannot spawn each other — that is exactly why this orchestration lives in a
skill rather than inside the implementer.

Your job: drive a `docs/TODO/*.md` spec from start to **filed**, by sequencing
focused workers and handling the cross-agent glue yourself.

| Subagent                      | Role                                                      |
| ----------------------------- | --------------------------------------------------------- |
| `{{AGENT_PREFIX}}-implementer` | Phase code, gates, self-audit, commit per phase, report   |
| `{{AGENT_PREFIX}}-tester`      | Marker-registered tests, runs the suites, commits separately |
| `{{AGENT_PREFIX}}-documenter`  | Updates the docs the change invalidates                   |

Each worker returns a report. **You** read it and decide the next step.

---

## Step 0 — Resolve the spec

The argument is either a path/slug of an existing spec (**execution mode**) or a
description with no spec (**plan-then-execute**).

For plan-then-execute, spawn the implementer in Planning Mode, read the returned
path, show the user the spec and **confirm before executing**. Planning is cheap
to redo; a wrong spec is expensive to implement.

Then read the spec yourself. Extract status, priority, dependencies, phases and
every `- [ ]` task, and build a `TodoWrite` plan mirroring the phases.

**Refuse an agent-managed plan.** If its frontmatter says `auto_generated: true`
it is a derived artifact that a scheduled job rewrites wholesale — filing it
would leave a zombie, and hand-editing it is overwritten on the next run.

## Step 1 — Implement

Spawn the implementer with the spec path. Handle its report:

- A phase came back **blocked with no path forward** → stop and surface it. A
  half-filed feature is worse than an unfiled one.
- It reports an unanticipated prerequisite → resolve that first, then re-invoke
  for the affected phase only.

## Step 2 — Tests

Spawn the tester with the implementer's changed-file list.

- ✅ green → proceed.
- ❌ **code** bug → describe the failure back to the implementer, then re-run
  the tester. Loop until green.
- ⚠️ nothing testable (pure docs/infra) → proceed, and say so.

**Tests gate filing.** Never file until the tester is green or has explicitly
reported "nothing testable".

## Step 3 — Docs

Spawn the documenter with the same changed-file list. Collect its summary.

## Step 4 — File the plan (you do this, and it is mandatory)

The spec must leave `docs/TODO/`. One command does the whole sequence:

```bash
{{CLI}} docs file <slug> --category <category>
```

It refuses a plan with unchecked tasks (`(~operator)` and `(~deferred)` excepted)
and commits nothing — read the diff.

**Then repoint what cited it. This is where this flow historically leaked.** The
move breaks links in two directions at once: every relative link *inside* the
spec (`../reports/x.md` now needs `../../`) and every link elsewhere that
pointed at its old path.

```bash
{{CLI}} check doc-refs     # docs/* paths cited from source comments
{{CLI}} check doc-links    # relative markdown links, and #fragments
```

**Repoint, never delete.** A link whose target is genuinely gone gets its
sentence rewritten to name the successor, or de-linked to a backticked path plus
the commit that removed it.

Set `agent_value` (1–3) in the filed doc's frontmatter: `3` = key design
decisions, read before modifying this system; `2` = debugging context; `1` =
historical. Rating everything `3` makes the field useless.

## Step 5 — One docs commit, then one push

Stage every pending doc change together — task check-offs, the move, reference
fixes, the regenerated indexes, and each doc the documenter touched — as ONE
commit:

```
docs(<scope>): complete <feature> — update docs, file to implementations

- Marked docs/TODO/<slug>.md complete and moved to docs/implementations/<category>/
- Regenerated the indexes
- Repointed cross-document references
- <docs the documenter updated>
```

Then push — **once**. Every commit before it stays local. Committing is free; a
push to an open PR is what spends CI minutes. If a PR is already open and out of
draft, flip it back with `gh pr ready --undo <n>` first, so the corrective push
re-runs nothing.

Verify before reporting success:

```bash
ls docs/TODO/<slug>.md 2>&1 | grep -q "No such file" && echo "✅ filed" || echo "❌ NOT filed"
{{CLI}} docs index --check
```

---

## Orchestration rules

1. **You sequence; the workers execute.** Never ask a worker to invoke another —
   they can't. All handoffs route through you.
2. **One worker at a time.** Each stage depends on the previous one's output,
   and they share files and commit history. Do not parallelize them.
3. **Tests gate filing.**
4. **Filing is yours and is mandatory.** The spec must never exist in both trees.
5. **Commit per phase, push once.** A phase boundary is a commit point, never a
   push point.
6. Any hard blocker → **stop and surface it**.
7. **Stay in the primary checkout** unless another agent is already editing it,
   or the work genuinely needs its own branch. Rule 2 keeps the workers serial,
   so ordinary work has nothing to collide with and needs no tree of its own.
   Taking a worktree by reflex reintroduces branch-and-PR ceremony for nothing.
