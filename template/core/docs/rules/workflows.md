# Implementation Workflow

The standard phases for any feature or change. Skip a phase only when it is genuinely empty
— not because the change feels small.

## Phase 1 — Planning & Context

1. Read the requirement carefully; restate what "done" means.
2. Identify which layers are affected (API, UI, data, infra, CLI).
3. Load only the docs you need — via `.github/DOCS_INDEX.md`, never all at once.
4. Identify **now** which docs will need updating afterwards. Deciding this at the end is how
   docs rot.

## Phase 2 — Implementation

5. Make focused changes that follow the Critical Rules in `AGENTS.md`.
6. If you added a command: update the `cli/` package in the same commit.
7. If you added a config value: add it to `.env.example` in the same commit.

## Phase 3 — Quality Checks

8. Run the blocking lint set (see `docs/rules/{{LANG_RULES}}.md`).
9. Run the type checker whole-project.
10. For a deeper pass, run `/code-review` from the main session.

## Phase 4 — Documentation

11. Update every doc identified in Phase 1.
12. A new `docs/*.md` gets registered in `AGENTS.md` **and** `.github/DOCS_INDEX.md`.

## Phase 5 — Testing

13. `{{CLI}} test <suite>` — all tests must pass before committing.
14. New behaviour gets new tests, with the right suite marker.
15. Zero failures for core functionality. A known-flaky test is a bug, not a fact of life.

## Phase 6 — Commit

16. Bundle all related files into ONE conventional commit.
17. Commit autonomously. When the whole task is complete and checks pass, push autonomously.

## Phase 7 — Release (when a tag is cut)

18. Release Please opens the release PR from the conventional commits. A human merges it.
19. Cutting a release **closes the report window** — see `docs/rules/docs.md`.
