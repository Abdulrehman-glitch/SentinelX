"""Tests for the CI Gate — the aggregating required status check.

The gate is the only thing standing between `main` and a merge, and its whole
job is to work out which path-filtered workflows a diff should have started.
Getting that mapping wrong in either direction is expensive: too narrow and a
broken component merges, too wide and a pull request hangs on a workflow that
was never going to run. So the mapping is pinned here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / ".github" / "scripts" / "ci_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("ci_gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


@pytest.fixture()
def workflows(monkeypatch):
    """The repository's real workflow definitions, loaded from the repo root."""
    monkeypatch.chdir(REPO_ROOT)
    return gate.load_workflows()


class TestGlobToRegex:
    @pytest.mark.parametrize(
        ("pattern", "path", "matches"),
        [
            ("backend/**", "backend/app/main.py", True),
            ("backend/**", "backend/Dockerfile", True),
            ("backend/**", "frontend/src/App.tsx", False),
            ("backend/**", "docs/backend/notes.md", False),
            ("agents/ios-native/ios/**", "agents/ios-native/ios/Sources/App.swift", True),
            ("agents/ios-native/ios/**", "agents/ios-native/server/main.py", False),
            (".github/workflows/backend.yml", ".github/workflows/backend.yml", True),
            (".github/workflows/backend.yml", ".github/workflows/frontend.yml", False),
        ],
    )
    def test_matching(self, pattern, path, matches):
        assert bool(gate.glob_to_regex(pattern).match(path)) is matches

    def test_single_star_does_not_cross_a_slash(self):
        assert gate.glob_to_regex("backend/*").match("backend/main.py")
        assert not gate.glob_to_regex("backend/*").match("backend/app/main.py")


class TestExpectedWorkflows:
    def test_backend_change_pulls_in_backend_and_container(self, workflows):
        got = gate.expected(["backend/app/main.py"], workflows)
        assert got == {
            ".github/workflows/backend.yml",
            ".github/workflows/docker.yml",
        }

    def test_migration_change_pulls_in_backend_and_container(self, workflows):
        got = gate.expected(["migrations/2026-08-21_browser_sessions.sql"], workflows)
        assert got == {
            ".github/workflows/backend.yml",
            ".github/workflows/docker.yml",
        }

    def test_test_change_pulls_in_backend_only(self, workflows):
        got = gate.expected(["tests/backend/test_auth_sessions.py"], workflows)
        assert got == {".github/workflows/backend.yml"}

    def test_frontend_change_is_isolated(self, workflows):
        got = gate.expected(["frontend/src/App.tsx"], workflows)
        assert got == {".github/workflows/frontend.yml"}

    def test_docs_only_change_expects_nothing(self, workflows):
        """The case that used to make a required check hang forever."""
        got = gate.expected(["docs/adr/0006-example.md", "README.md"], workflows)
        assert got == set()

    def test_a_workflow_edit_triggers_its_own_workflow(self, workflows):
        got = gate.expected([".github/workflows/android.yml"], workflows)
        assert got == {".github/workflows/android.yml"}

    def test_the_gate_never_waits_for_itself(self, workflows):
        got = gate.expected([".github/workflows/ci-gate.yml"], workflows)
        assert ".github/workflows/ci-gate.yml" not in got

    def test_manual_publish_workflow_is_never_expected(self, workflows):
        got = gate.expected(["backend/app/main.py", "backend/Dockerfile"], workflows)
        assert ".github/workflows/container-publish.yml" not in got

    def test_multi_component_change_unions_the_expectations(self, workflows):
        got = gate.expected(
            ["backend/app/main.py", "frontend/src/App.tsx", "agents/desktop-python/x.py"],
            workflows,
        )
        assert got == {
            ".github/workflows/backend.yml",
            ".github/workflows/docker.yml",
            ".github/workflows/frontend.yml",
            ".github/workflows/desktop-agent.yml",
        }


def _run(path, *, number, status="completed", conclusion="success", event="pull_request"):
    return {
        "path": path,
        "name": path,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "run_number": number,
        "run_attempt": 1,
        "id": number * 100,
        "html_url": f"https://example.invalid/{number}",
    }


class TestRelevantRuns:
    def _patch(self, monkeypatch, runs):
        monkeypatch.setattr(gate, "api", lambda _path: {"workflow_runs": runs})

    def test_latest_run_per_workflow_wins(self, monkeypatch):
        self._patch(
            monkeypatch,
            [
                _run("a.yml", number=1, conclusion="failure"),
                _run("a.yml", number=2, conclusion="success"),
            ],
        )
        got = gate.relevant_runs("sha", "o/r")
        assert got["a.yml"]["conclusion"] == "success"

    def test_a_superseded_cancelled_run_does_not_mask_the_rerun(self, monkeypatch):
        """`cancel-in-progress` cancels the old run; only the newest one counts."""
        self._patch(
            monkeypatch,
            [
                _run("a.yml", number=5, status="completed", conclusion="cancelled"),
                _run("a.yml", number=6, status="completed", conclusion="success"),
            ],
        )
        assert gate.relevant_runs("sha", "o/r")["a.yml"]["conclusion"] == "success"

    def test_dependabot_runs_are_ignored(self, monkeypatch):
        self._patch(
            monkeypatch,
            [
                _run("dynamic/dependabot/dependabot-updates", number=1, conclusion="failure"),
                _run("dynamic/dependabot/update-graph", number=1, conclusion="failure"),
            ],
        )
        assert gate.relevant_runs("sha", "o/r") == {}

    def test_codeql_is_tracked(self, monkeypatch):
        self._patch(
            monkeypatch,
            [_run("dynamic/github-code-scanning/codeql", number=1, event="dynamic")],
        )
        assert "dynamic/github-code-scanning/codeql" in gate.relevant_runs("sha", "o/r")

    def test_the_gate_and_the_publish_workflow_are_ignored(self, monkeypatch):
        self._patch(
            monkeypatch,
            [
                _run(".github/workflows/ci-gate.yml", number=1),
                _run(".github/workflows/container-publish.yml", number=1),
            ],
        )
        assert gate.relevant_runs("sha", "o/r") == {}

    def test_push_runs_are_ignored(self, monkeypatch):
        """A push run on the same SHA is not the pull request's signal."""
        self._patch(monkeypatch, [_run("a.yml", number=1, event="push")])
        assert gate.relevant_runs("sha", "o/r") == {}


class TestArtifactPolicy:
    def test_the_real_repository_satisfies_the_policy(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        assert gate.cmd_policy() == 0

    def test_an_unguarded_upload_is_rejected(self, tmp_path, monkeypatch):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "bad.yml").write_text(
            "name: Bad\non:\n  pull_request:\njobs:\n"
            "  j:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/upload-artifact@v4\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert gate.cmd_policy() == 1

    def test_a_dispatch_guarded_upload_is_allowed(self, tmp_path, monkeypatch):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ok.yml").write_text(
            "name: Ok\non:\n  pull_request:\njobs:\n"
            "  j:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/upload-artifact@v4\n"
            "        if: github.event_name == 'workflow_dispatch'\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert gate.cmd_policy() == 0

    def test_a_docker_build_without_the_record_opt_out_is_rejected(self, tmp_path, monkeypatch):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "img.yml").write_text(
            "name: Img\non:\n  push:\n    branches: [main]\njobs:\n"
            "  j:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: docker/build-push-action@v6\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        assert gate.cmd_policy() == 1
