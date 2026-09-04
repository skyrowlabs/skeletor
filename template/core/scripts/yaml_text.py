#!/usr/bin/env python3
"""Read a YAML file as code, with its comments blanked.

Every check that greps a workflow matches against text, and **a comment is
text**. Two shipped gates read comments as code and both passed while the thing
they guard was absent:

* `check_workflow_drift.py` required `actions/setup-python` in any job that
  stands the stack up. A job with no such step, carrying
  `# TODO: we should add actions/setup-python here one day`, was green. The
  string most likely to appear in a job that has **not** done the thing is a
  comment saying it should — so the false pass is perfectly correlated with the
  defect, which is the worst arrangement available.
* `tests/test_ci_draft_gate.py` asserted `"ready_for_review" in ci.yml`. Deleting
  the trigger and leaving `# note: ready_for_review used to be here` kept all
  five of its tests green. That gate exists specifically to catch a deleted
  trigger.

jam.sense supplied the general form, from a naive grep that hit their
`cli/worktree.py` twice — on an error message and a docstring — while missing
the call it was looking for: **a detector validated by "it found the file I
expected" is not validated; it has to find the site.**

This repository already held the rule twice and had not joined it up.
`check_output_discipline.py` masks prose before scanning and `check_doc_links.py`
blanks fences and comments before matching — so the two checkers that scan for a
*mistake* were careful, and the two that scan for a *requirement* were not. That
asymmetry is not a coincidence: a false positive gets reported and fixed, and a
false negative is silence.

One home rather than a copy per consumer, for the reason `scripts/allowlist.py`
exists: four copies of one parser is how a shared format drifts, since each copy
is correct about its own caller's input and nothing compares them.
"""

from __future__ import annotations

from pathlib import Path


def uncommented(text: str) -> str:
    """`text` with YAML comments removed, one line per line.

    Blanked rather than deleted so line numbers keep meaning something, and a
    `#` inside quotes is left alone so `run: echo "# heading"` stays code.

    Deliberately not a YAML parser. This runs on any host with no dependency,
    it is checking text that a parser would have already normalised past, and a
    mis-strip fails loudly — the required step goes missing — rather than
    passing wrongly, which is the direction that matters here.
    """
    out = []
    for line in text.splitlines():
        quote = ""
        cut = None
        for i, char in enumerate(line):
            if quote:
                if char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "#":
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def read_uncommented(path: Path) -> str:
    """A workflow's code, with its comments gone."""
    return uncommented(path.read_text(encoding="utf-8"))
