"""The one predicate for *does unversioned content reach this render*.

Two doors write a record that names a skeletor ref, and until `v0.10.3` only one
of them asked this question. `bin/skeletor-upgrade` refused a dirty base before
writing anything; `bin/skeletor-new` — the door that creates `.skeletor.json` in
the first place — had no guard at all.

The cost is worse at the scaffold end, and stash.flow measured every part of it.
An untracked file under `template/` renders into the tree and is recorded in the
manifest, while `git describe --dirty` stays **clean**, because it is
untracked-blind. So the tree carries a manifest naming a base no checkout can
reproduce, with nothing in it to say a dirty checkout was ever involved — and
every later upgrade, from anybody, refuses permanently:

    ❌ .skeletor.json disagrees with the base it names (1 file(s)):
       · ZZ_PLANT.md: recorded, but the base render does not produce it

The upgrade already prints the reasoning for its own end: *"would record hashes
of a render that exists in no commit, so the next run resolves the recorded ref,
renders something else, and refuses — permanently."* Every word of that was true
about the scaffolder, in a file the adopter then commits, failing later in a
different tree for a different person.

**The justification had already travelled and the mechanism had not.**
`reaches_a_render` called its own scoping *"the one already accepted for the
scaffold end of the same pipe"* — the argument came from here; the code never
did. That is this repository's own recurring failure, one file over.

This module exists so there is one predicate rather than an agreement between
two. It is itself a render input, because editing it changes what a scaffold
refuses.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

#: What a render reads. `bin/render_guard.py` is here because a change to this
#: file changes which dirt counts — leaving it out would make the guard unable
#: to see edits to itself, which is the shape of every registry bug this project
#: is built to avoid.
RENDER_INPUTS = ("template/", "bin/skeletor-new", "bin/render_guard.py")


def reaches_a_render(path: str) -> bool:
    """Can uncommitted work at this path change what a render produces?

    The guard used to count **every** uncommitted file, which was right about
    untracked files and wrong about which ones. The justification was always
    scoped — `copy_overlay` walks `template/`, so an untracked file *there* is
    rendered as readily as a committed one — and the code applied it to the
    whole repository. So one untracked `notes.md` at this repo's root, which no
    render can read, refused every adopter in a five-repository round: three
    cloned at a tag to get past it and one more was warned off.

    node-zero's predicate: **does the dirt intersect what this render reads.**
    It still refuses the case the guard exists for — an uncommitted `ci.yml`
    under `template/`, which is how proto.pilot's manifest was poisoned.

    A rename reports as `old -> new`, and either side landing in a render input
    is enough: moving a file into `template/` adds it to the render, and moving
    one out removes it.

    It is deliberately conservative at `template/` root, which is matched and is
    not an overlay source — `copy_overlay` runs per overlay — so a file dropped
    directly there is called render-reaching and renders nothing. Right for a
    refusal, and worth knowing when reading a report.
    """
    return any(part.startswith(RENDER_INPUTS) for part in path.split(" -> "))


def uncommitted(target: Path, *, untracked: bool = False) -> Optional[List[str]]:
    """Paths with uncommitted changes — or None if git cannot say.

    The `untracked` flag is not a preference, it is the difference between two
    questions. For a **target tree**, untracked files do not matter: one does
    not appear in `git diff` and nothing will remove it, so it cannot make the
    result unreadable — only tracked work interleaves. For a **checkout that
    renders**, they matter most of all: `copy_overlay` walks the template
    directory, so an untracked file under `template/` is rendered as readily as
    a committed one, and is exactly as absent from history.

    Its render callers then filter to `reaches_a_render`. The scoping belongs to
    the question rather than to the enumeration — a target's callers want the
    whole set.
    """
    result = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain", f"--untracked-files={'all' if untracked else 'no'}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return sorted(line[3:] for line in result.stdout.splitlines() if line.strip())


def render_dirt(checkout: Path) -> List[str]:
    """Uncommitted content this checkout would render, untracked included.

    Both halves matter and `git describe --dirty` gets both wrong — it is
    untracked-blind and repo-wide, which are precisely the two properties this
    predicate exists to fix. It has re-entered through a version string once
    already, in the condition guarding a sentence that had the string in it.
    """
    return [path for path in uncommitted(checkout, untracked=True) or [] if reaches_a_render(path)]
