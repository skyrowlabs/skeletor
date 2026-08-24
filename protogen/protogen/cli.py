"""The command line.

    proto new "an app for tracking camping gear across trips"
    proto add "let people mark items as packed"
    proto up | down | logs | test | spec | doctor
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import click

from protogen import __version__, build as builder
from protogen.baseline import standard_screens
from protogen.llm import LLMError, build_llm
from protogen.passes import PassContext, intake
from protogen.render import render_skeleton
from protogen.runner import SubprocessRunner, docker_available
from protogen.spec import SPEC_DIR, SPEC_FILENAME, Screen, Spec
from protogen.verify import Verifier

PORT_RANGE = range(8080, 8180)


def _echo(message: str) -> None:
    click.echo(message)


def free_port(preferred: int | None = None) -> int:
    """First port nothing is listening on.

    Prototypes accumulate; the third one colliding with the first is the most
    predictable way for a generated app to look broken on arrival.
    """
    candidates = [preferred, *PORT_RANGE] if preferred else list(PORT_RANGE)
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise click.ClickException(f"no free port in {PORT_RANGE.start}-{PORT_RANGE.stop}")


def _project(directory: str | None) -> Path:
    path = Path(directory or ".").resolve()
    if not (path / SPEC_DIR / SPEC_FILENAME).exists():
        raise click.ClickException(
            f"{path} is not a protogen project (no {SPEC_DIR}/{SPEC_FILENAME})"
        )
    return path


def _verifier(project_dir: Path, spec: Spec) -> Verifier:
    return Verifier(project_dir, spec.port, SubprocessRunner())


def _compose(project_dir: Path, *args: str) -> int:
    return subprocess.call(["docker", "compose", *args], cwd=str(project_dir))  # noqa: S603


@click.group()
@click.version_option(__version__, prog_name="protogen")
def main() -> None:
    """Turn an idea and a little direction into a running prototype."""


@main.command()
@click.argument("idea")
@click.option("--dir", "directory", default=None, help="Target directory (default: ./<slug>).")
@click.option("--direction", default="", help="Extra steer: look, feel, emphasis.")
@click.option("--port", type=int, default=None, help="Host port (default: first free from 8080).")
@click.option("--attempts", type=int, default=3, show_default=True, help="Repair attempts before handing back a RUNBOOK.")
@click.option("--offline", is_flag=True, help="Deterministic baseline generator; no API calls.")
@click.option("--no-verify", is_flag=True, help="Generate but do not boot or test.")
@click.option("--no-git", is_flag=True, help="Do not git init the generated tree.")
@click.option("--yes", "-y", is_flag=True, help="Skip the spec review checkpoint.")
def new(
    idea: str,
    directory: str | None,
    direction: str,
    port: int | None,
    attempts: int,
    offline: bool,
    no_verify: bool,
    no_git: bool,
    yes: bool,
) -> None:
    """Generate a new prototype from IDEA."""
    llm = build_llm(offline=offline)

    if not no_verify:
        ok, why = docker_available(SubprocessRunner())
        if not ok:
            # Said now rather than after the generation passes, because after
            # is when the tokens have already been spent.
            raise click.ClickException(
                f"{why}. Start Docker, or pass --no-verify to generate without booting."
            )

    _echo("intake...")
    ctx = PassContext(project_dir=Path("."), change=direction)
    try:
        if llm.offline:
            data = intake.offline(idea, ctx)
        else:
            system, user = intake.build(idea, ctx)
            data = llm.structured(
                system=system, user=user, schema=intake.SCHEMA, label=intake.NAME
            )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    spec = Spec.model_validate(data)
    spec.port = free_port(port)
    spec.direction = direction or spec.direction
    spec.protogen_version = __version__
    if not spec.screens:
        # Screens are the contract the smoke tests and the routes are both
        # generated from, so an empty list is not something to pass along.
        spec.screens = [Screen(**s) for s in standard_screens(spec)]

    target = Path(directory).resolve() if directory else Path.cwd() / spec.slug

    _echo("")
    _echo(spec.summary())
    _echo(f"\n  -> {target}")
    _echo("")
    if not yes and not click.confirm("Generate this?", default=True):
        raise click.Abort()

    if target.exists() and any(target.iterdir()):
        raise click.ClickException(f"{target} exists and is not empty")

    _echo("rendering skeleton...")
    written = render_skeleton(spec, target)
    _echo(f"  {len(written)} skeleton files")
    spec.save(target)

    ctx = PassContext(project_dir=target, change=direction)
    try:
        builder.generate(spec, ctx, llm, log=_echo)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    if not no_git:
        _git_init(target)

    if no_verify:
        _echo(f"\nGenerated (not verified). `cd {target} && make up`")
        return

    _finish(spec, ctx, llm, target, attempts)


@main.command()
@click.argument("change")
@click.option("--dir", "directory", default=None, help="Project directory (default: cwd).")
@click.option("--attempts", type=int, default=3, show_default=True)
@click.option("--offline", is_flag=True)
@click.option("--no-verify", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def add(
    change: str,
    directory: str | None,
    attempts: int,
    offline: bool,
    no_verify: bool,
    yes: bool,
) -> None:
    """Apply CHANGE to an existing prototype and re-verify it."""
    target = _project(directory)
    spec = Spec.load(target)
    llm = build_llm(offline=offline)
    if llm.offline:
        raise click.ClickException(
            "`add` needs the model: the baseline generator cannot read a change request."
        )

    _echo("amending spec...")
    system, user = intake.build_amend(spec, change)
    try:
        data = llm.structured(
            system=system, user=user, schema=intake.SCHEMA, label="amend"
        )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    updated = Spec.model_validate(data)
    # Identity is not the model's to change: the slug is the database name and
    # the port is what the user has open in a tab.
    updated.slug, updated.port = spec.slug, spec.port
    updated.protogen_version = __version__

    _echo("")
    _echo(updated.summary())
    _echo("")
    if not yes and not click.confirm("Apply this?", default=True):
        raise click.Abort()

    updated.save(target)
    ctx = PassContext(project_dir=target, change=change)
    try:
        builder.generate(updated, ctx, llm, log=_echo)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    if no_verify:
        _echo("\nRegenerated (not verified).")
        return
    _finish(updated, ctx, llm, target, attempts)


def _finish(spec: Spec, ctx: PassContext, llm, target: Path, attempts: int) -> None:
    outcome = builder.drive_to_green(
        spec, ctx, llm, _verifier(target, spec), attempts=attempts, log=_echo
    )
    if outcome.ok:
        runbook = target / "RUNBOOK.md"
        if runbook.exists():
            runbook.unlink()  # a stale runbook reads as a live problem
        _echo(f"\n  {spec.name} is up:  http://localhost:{spec.port}")
        _echo(f"  {target}")
        return

    path = builder.write_runbook(target, spec, outcome)
    _echo(
        f"\n  Could not get to green in {attempts} attempt(s). The tree is at\n"
        f"  {target}, and what is broken is written down in {path.name}."
    )
    sys.exit(1)


def _git_init(target: Path) -> None:
    """First commit is the pristine generation, so `git diff` shows the user
    their own edits rather than the whole app."""
    try:
        for argv in (
            ["git", "init", "-q"],
            ["git", "add", "-A"],
            ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "generated by protogen"],
        ):
            subprocess.run(argv, cwd=str(target), check=True, capture_output=True)  # noqa: S603
    except (subprocess.CalledProcessError, FileNotFoundError):
        _echo("  (git init skipped)")


@main.command(name="spec")
@click.option("--dir", "directory", default=None)
@click.option("--json", "as_json", is_flag=True, help="Print the raw spec.")
def show_spec(directory: str | None, as_json: bool) -> None:
    """Show this project's spec."""
    target = _project(directory)
    spec = Spec.load(target)
    click.echo(
        (target / SPEC_DIR / SPEC_FILENAME).read_text() if as_json else spec.summary()
    )


@main.command()
@click.option("--dir", "directory", default=None)
def up(directory: str | None) -> None:
    """Start the app."""
    target = _project(directory)
    spec = Spec.load(target)
    code = _compose(target, "up", "-d", "--build")
    if code == 0:
        _echo(f"http://localhost:{spec.port}")
    sys.exit(code)


@main.command()
@click.option("--dir", "directory", default=None)
def down(directory: str | None) -> None:
    """Stop the app and drop its data."""
    sys.exit(_compose(_project(directory), "down", "-v"))


@main.command()
@click.option("--dir", "directory", default=None)
def logs(directory: str | None) -> None:
    """Follow the app logs."""
    sys.exit(_compose(_project(directory), "logs", "-f", "app"))


@main.command()
@click.option("--dir", "directory", default=None)
def test(directory: str | None) -> None:
    """Run the smoke tests inside the container."""
    sys.exit(_compose(_project(directory), "exec", "-T", "app", "pytest", "-q"))


@main.command()
def doctor() -> None:
    """Check that protogen can actually do its job here."""
    ok = True

    docker_ok, why = docker_available(SubprocessRunner())
    _echo(f"{'ok  ' if docker_ok else 'FAIL'} docker: {why}")
    ok &= docker_ok

    try:
        import anthropic  # noqa: F401

        _echo("ok   anthropic sdk: installed")
    except ImportError:
        _echo("FAIL anthropic sdk: not installed (`pip install anthropic`)")
        ok = False

    try:
        from protogen.llm import ClaudeLLM

        llm = ClaudeLLM()
        _echo(f"ok   credentials: resolved (model {llm.model}, effort {llm.effort})")
    except Exception as exc:  # noqa: BLE001
        _echo(f"FAIL credentials: {exc}")
        _echo("     set ANTHROPIC_API_KEY, or run `ant auth login`")
        ok = False

    port = None
    try:
        port = free_port()
        _echo(f"ok   ports: {port} is free")
    except click.ClickException as exc:
        _echo(f"FAIL ports: {exc}")
        ok = False

    _echo("")
    _echo("ready" if ok else "not ready -- `--offline --no-verify` still works for a dry run")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
