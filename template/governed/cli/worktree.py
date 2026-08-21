"""``{{CLI}} worktree`` — a second checkout, so two agents never share one branch.

A linked worktree is the answer to "I need a different branch" in a tree
somebody else is standing in. It costs disk and a provisioning step; it does not
cost the other agent their uncommitted work, which a `git switch` does.

**Remove it when the work is done.** A stranded tree holds hundreds of megabytes
and possibly a whole running stack.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from cli.helpers import PROJECT_ROOT, fail, git, ok, run, warn


@click.group()
def worktree() -> None:
    """Linked worktrees — one checkout per branch."""


@worktree.command()
@click.argument("path")
@click.option("-b", "--branch", help="branch to create (defaults to the directory name)")
@click.option("--base", default="{{BASE_BRANCH}}", show_default=True)
def new(path: str, branch: str, base: str) -> None:
    """Create a worktree with its own branch, .env and scratch space."""
    target = Path(path).expanduser().resolve()
    branch = branch or target.name

    if target.exists():
        fail(f"{target} already exists")
        sys.exit(1)

    run(["git", "fetch", "origin", base])
    if run(["git", "worktree", "add", "-b", branch, str(target), f"origin/{base}"]).returncode != 0:
        fail("git worktree add failed")
        sys.exit(1)

    # The .env is untracked, so a new tree has none — and a tree that cannot
    # boot is a tree whose suite silently skips everything.
    env = PROJECT_ROOT / ".env"
    if env.exists():
        shutil.copy2(env, target / ".env")
        print(f"  · copied .env")
    (target / "tmp").mkdir(exist_ok=True)

    ok(f"worktree at {target} on branch '{branch}'")
    print(f"\n  cd {target}")
    print(f"  ./{{CLI}} check pre-push")
    print(f"\n  When you are done:  {{CLI}} worktree drop {target}")


@worktree.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="remove even with uncommitted or unpushed work")
def drop(path: str, force: bool) -> None:
    """Remove a worktree, refusing if it still holds work.

    The refusal on unpushed commits is the important half: a detached
    worktree's commits are reachable from nothing but its own HEAD, so that
    refusal is the only thing between them and silent deletion.
    """
    target = Path(path).expanduser().resolve()
    if not target.exists():
        fail(f"no such worktree: {target}")
        sys.exit(1)

    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(target), capture_output=True, text=True).stdout.strip()
    if dirty and not force:
        fail(f"{target} has {len(dirty.splitlines())} uncommitted change(s) — refusing")
        print("   That work belongs to somebody. Commit it, or pass --force if you are sure.")
        sys.exit(1)

    unpushed = subprocess.run(
        ["git", "log", "--branches", "--not", "--remotes", "--oneline"], cwd=str(target), capture_output=True, text=True
    ).stdout.strip()
    if unpushed and not force:
        fail(f"{target} holds {len(unpushed.splitlines())} commit(s) on no remote:")
        for line in unpushed.splitlines()[:5]:
            print(f"   · {line}")
        print("   These are reachable from nothing but this tree's HEAD. Push them, or --force.")
        sys.exit(1)

    run(["git", "worktree", "remove", *(["--force"] if force else []), str(target)])
    ok(f"removed {target}")


@worktree.command(name="list")
def list_cmd() -> None:
    """Every worktree, and whether it holds anything."""
    print(git("worktree", "list"))


@worktree.command()
def holders() -> None:
    """Who is holding the primary tree right now."""
    sys.exit(subprocess.run([sys.executable, "scripts/tree_lock.py"], cwd=str(PROJECT_ROOT)).returncode)
