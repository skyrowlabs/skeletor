# {{PROJECT_NAME}}

**The rules for this repository are in [`AGENTS.md`](AGENTS.md). Read that file.**

---

This file exists because some tools look for it by name. It is deliberately a
pointer and **not a copy**: `AGENTS.md` is the convention every agent tool
reads, and two files stating the same rules drift within the week — the copy
that is wrong being whichever one happened to get loaded.

**Add nothing here.** A rule that lives only in this file is a rule the rest of
the tooling cannot see: `{{CLI}} check docs` indexes `AGENTS.md` as one of the
two agent-facing tables, and `.github/DOCS_INDEX.md` routes to it.
