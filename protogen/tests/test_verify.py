from __future__ import annotations

from fakes import FakeRunner

from protogen.verify import Verifier

HEALTHY = (200, '{"ok": true, "app": "Gear List"}')
REFUSED = (0, "connection refused")


def make(runner, getter, **kwargs) -> Verifier:
    return Verifier(
        project_dir=kwargs.pop("project_dir", "/tmp/x"),
        port=8099,
        runner=runner,
        getter=getter,
        sleep=lambda _: None,
        health_timeout=kwargs.pop("health_timeout", 0.0),
        **kwargs,
    )


def test_green_run_reports_ok():
    result = make(FakeRunner(), lambda url, timeout: HEALTHY).verify()
    assert result.ok and result.stage == "tests"
    assert "8099" in result.summary


def test_build_failure_stops_before_anything_else():
    runner = FakeRunner([(["docker", "compose", "up"], (1, "", "no such image"))])
    result = make(runner, lambda url, timeout: HEALTHY).verify()
    assert not result.ok and result.stage == "build"
    assert "no such image" in result.output
    # No point polling a stack that never started.
    assert not runner.ran("docker", "compose", "exec")


def test_health_timeout_is_reported_with_logs():
    runner = FakeRunner([(["docker", "compose", "logs"], (0, "ImportError: no module app.x", ""))])
    result = make(runner, lambda url, timeout: REFUSED).verify()
    assert not result.ok and result.stage == "health"
    # The logs are the point: a boot failure says nothing useful anywhere else.
    assert "ImportError" in result.logs
    assert not runner.ran("docker", "compose", "exec")


def test_health_accepts_only_a_true_ok_field():
    runner = FakeRunner()
    result = make(runner, lambda url, timeout: (200, '{"ok": false}')).verify()
    assert not result.ok and result.stage == "health"


def test_failing_tests_carry_output_and_logs():
    runner = FakeRunner(
        [
            (["docker", "compose", "exec"], (1, "E  assert 200 == 404", "")),
            (["docker", "compose", "logs"], (0, "GET /trips/99999999 200", "")),
        ]
    )
    result = make(runner, lambda url, timeout: HEALTHY).verify()
    assert not result.ok and result.stage == "tests"
    assert "assert 200 == 404" in result.output
    assert "GET /trips/99999999" in result.logs


def test_up_tears_the_stack_down_first():
    """create_all() cannot alter an existing table, so a repair that changed a
    model would otherwise be verified against the previous schema."""
    runner = FakeRunner()
    make(runner, lambda url, timeout: HEALTHY).up()
    compose = [c for c in runner.calls if c[:2] == ["docker", "compose"]]
    assert compose[0][2:5] == ["down", "-v", "--remove-orphans"]
    assert compose[1][2:5] == ["up", "-d", "--build"]


def test_tests_run_without_a_tty():
    """Without -T this hangs forever in every non-interactive shell, which is
    every shell protogen runs in."""
    runner = FakeRunner()
    make(runner, lambda url, timeout: HEALTHY).run_tests()
    assert runner.ran("docker", "compose", "exec", "-T", "app", "pytest", "-q")
