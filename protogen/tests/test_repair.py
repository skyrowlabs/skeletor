"""The repair loop is where a generator becomes a tool that hands back running
software, so its failure modes get tested rather than hoped about."""

from __future__ import annotations

from fakes import FakeLLM, FakeVerifier

from protogen.build import drive_to_green, write_runbook
from protogen.passes import PassContext
from protogen.render import render_skeleton
from protogen.verify import VerifyResult

GREEN = VerifyResult(True, "tests", "green -- app is up on http://localhost:8099")
RED_TESTS = VerifyResult(
    False, "tests", "the smoke tests failed",
    "E  assert 500 == 200", "jinja2.exceptions.UndefinedError: 'rows' is undefined",
)
RED_BUILD = VerifyResult(False, "build", "could not build", "no such image")

THREE_TESTS = (
    "def test_a():\n    assert True\n\n\n"
    "def test_b():\n    assert True\n\n\n"
    "def test_c():\n    assert True\n"
)


def project(spec, tmp_path, smoke: str = THREE_TESTS):
    render_skeleton(spec, tmp_path)
    (tmp_path / "tests" / "test_smoke.py").write_text(smoke)
    return PassContext(project_dir=tmp_path)


def patch(path: str, content: str, notes: str = "fixed it") -> dict:
    return {"files": [{"path": path, "content": content}], "notes": notes}


def test_a_repaired_tree_reports_green(spec, tmp_path):
    ctx = project(spec, tmp_path)
    llm = FakeLLM([patch("app/routes.py", "router = 1\n")])
    verifier = FakeVerifier([RED_TESTS, GREEN])

    outcome = drive_to_green(spec, ctx, llm, verifier, attempts=3, log=lambda _: None)

    assert outcome.ok and outcome.attempts == 2
    assert verifier.runs == 2
    assert outcome.repairs and "tests" in outcome.repairs[0]
    assert "router = 1" in (tmp_path / "app" / "routes.py").read_text()


def test_the_repair_pass_is_shown_the_logs(spec, tmp_path):
    """The boring 80% of first-run failures say nothing useful in the assertion
    and say exactly what is wrong in the log."""
    ctx = project(spec, tmp_path)
    llm = FakeLLM([patch("app/routes.py", "router = 1\n")])
    drive_to_green(spec, ctx, llm, FakeVerifier([RED_TESTS, GREEN]), log=lambda _: None)

    prompt = llm.calls[0]["user"]
    assert "UndefinedError" in prompt
    assert "assert 500 == 200" in prompt
    assert "[tests]" in prompt


def test_attempts_are_bounded_and_the_tree_is_handed_back(spec, tmp_path):
    ctx = project(spec, tmp_path)
    llm = FakeLLM([patch("app/routes.py", "a = 1\n"), patch("app/routes.py", "a = 2\n")])
    verifier = FakeVerifier([RED_TESTS, RED_TESTS, RED_TESTS])

    outcome = drive_to_green(spec, ctx, llm, verifier, attempts=2, log=lambda _: None)

    assert not outcome.ok
    assert verifier.runs == 3  # the initial run plus one per repair
    assert len(outcome.repairs) == 2


def test_a_runbook_records_what_is_broken(spec, tmp_path):
    ctx = project(spec, tmp_path)
    outcome = drive_to_green(
        spec, ctx, FakeLLM([]), FakeVerifier([RED_BUILD]), attempts=0, log=lambda _: None
    )
    assert not outcome.ok

    path = write_runbook(tmp_path, spec, outcome)
    body = path.read_text()
    assert "**build**" in body
    assert "no such image" in body
    assert "docker compose logs -f app" in body


def test_a_repair_that_deletes_tests_is_reverted(spec, tmp_path):
    """The one failure mode the prompt cannot prevent and nobody would notice:
    green because there is nothing left to fail."""
    ctx = project(spec, tmp_path)
    llm = FakeLLM(
        [patch("tests/test_smoke.py", "def test_a():\n    assert True\n", "trimmed")]
    )
    outcome = drive_to_green(
        spec, ctx, llm, FakeVerifier([RED_TESTS, GREEN]), attempts=1, log=lambda _: None
    )

    restored = (tmp_path / "tests" / "test_smoke.py").read_text()
    assert restored.count("def test_") == 3
    assert "test deletion rejected" in outcome.repairs[0]


def test_a_repair_that_keeps_the_test_count_is_allowed(spec, tmp_path):
    ctx = project(spec, tmp_path)
    rewritten = THREE_TESTS.replace("assert True", "assert 1 == 1")
    llm = FakeLLM([patch("tests/test_smoke.py", rewritten, "corrected an assertion")])
    drive_to_green(
        spec, ctx, llm, FakeVerifier([RED_TESTS, GREEN]), attempts=1, log=lambda _: None
    )
    assert "assert 1 == 1" in (tmp_path / "tests" / "test_smoke.py").read_text()


def test_a_repair_with_no_changes_stops_the_loop(spec, tmp_path):
    """Offline mode cannot repair; spinning through the remaining attempts
    would just burn wall-clock to reach the same runbook."""
    ctx = project(spec, tmp_path)
    llm = FakeLLM([{"files": [], "notes": "cannot repair"}])
    verifier = FakeVerifier([RED_TESTS, GREEN, GREEN])

    outcome = drive_to_green(spec, ctx, llm, verifier, attempts=3, log=lambda _: None)

    assert not outcome.ok
    assert verifier.runs == 1
