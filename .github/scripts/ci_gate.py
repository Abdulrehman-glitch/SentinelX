#!/usr/bin/env python3
"""CI Gate — the one required status check on `main`.

Every component workflow here is path-filtered, so none of them reports on a
pull request that does not touch its component. Requiring any of them in branch
protection would leave such a PR pending forever. This job always runs, derives
from the workflow files themselves which component workflows the diff should
have started, waits for exactly those, and fails if any failed.

Two modes:
    policy  — static assertions that hold on every PR (artifact policy).
    wait    — discover and await the component workflows for this PR's head SHA.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

WORKFLOW_DIR = Path(".github/workflows")

# Never waited on: this job itself, the manual-only publish workflow, and
# Dependabot's own update jobs (they report on stale alerts, not on the diff).
EXCLUDED_PATHS = {
    ".github/workflows/ci-gate.yml",
    ".github/workflows/container-publish.yml",
}
EXCLUDED_PREFIXES = ("dynamic/dependabot/",)

WATCHED_EVENTS = {"pull_request", "dynamic"}

# How long a workflow has to register a run before we stop expecting new ones.
DISCOVERY_SECONDS = 240
POLL_SECONDS = 20
PASSING = {"success", "skipped", "neutral"}


def api(path: str) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    url = f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com')}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sentinelx-ci-gate",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_workflows() -> dict[str, dict]:
    """Map repo-relative workflow path -> parsed YAML."""
    out = {}
    for f in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        with f.open(encoding="utf-8") as fh:
            out[f.as_posix()] = yaml.safe_load(fh) or {}
    return out


def triggers(wf: dict) -> dict:
    """`on:` parses to the YAML 1.1 boolean True, so accept both spellings."""
    return wf.get("on") or wf.get(True) or {}


def glob_to_regex(pattern: str) -> re.Pattern:
    """GitHub path-filter globs: `*` stops at `/`, `**` crosses it."""
    parts, i = ["^"], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                parts.append(".*")
                i += 2
                continue
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(ch))
        i += 1
    parts.append("$")
    return re.compile("".join(parts))


def expected(changed: list[str], workflows: dict[str, dict]) -> set[str]:
    """Workflow paths whose pull_request filters match at least one changed file."""
    hit = set()
    for path, wf in workflows.items():
        if path in EXCLUDED_PATHS:
            continue
        trig = triggers(wf)
        if "pull_request" not in trig:
            continue
        pr = trig.get("pull_request")
        globs = pr.get("paths") if isinstance(pr, dict) else None
        # No `paths` key at all means the workflow runs on every PR.
        if not globs:
            hit.add(path)
            continue
        matchers = [glob_to_regex(g) for g in globs]
        if any(m.match(f) for f in changed for m in matchers):
            hit.add(path)
    return hit


def relevant_runs(sha: str, repo: str) -> dict[str, dict]:
    """Latest run per workflow path for this head SHA."""
    data = api(f"/repos/{repo}/actions/runs?head_sha={sha}&per_page=100")
    latest: dict[str, dict] = {}
    for run in data.get("workflow_runs", []):
        path = run.get("path", "")
        if path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PREFIXES):
            continue
        if run.get("event") not in WATCHED_EVENTS:
            continue
        key = (run.get("run_number", 0), run.get("run_attempt", 0), run.get("id", 0))
        prev = latest.get(path)
        if prev is None or key > prev["_key"]:
            latest[path] = {**run, "_key": key}
    return latest


def cmd_wait() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["HEAD_SHA"]
    changed = [
        line.strip()
        for line in Path(os.environ["CHANGED_FILES"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    workflows = load_workflows()
    want = expected(changed, workflows)

    print(f"Head SHA      : {sha}")
    print(f"Changed files : {len(changed)}")
    for f in changed[:40]:
        print(f"    {f}")
    if len(changed) > 40:
        print(f"    ... and {len(changed) - 40} more")
    print("Expected from the diff:")
    for p in sorted(want):
        print(f"    {p}")
    if not want:
        print("    (none — no component paths touched)")

    discovery_deadline = time.time() + DISCOVERY_SECONDS
    seen: set[str] = set()
    runs: dict[str, dict] = {}

    while True:
        try:
            runs = relevant_runs(sha, repo)
        except urllib.error.URLError as exc:  # transient API hiccup, keep polling
            print(f"  ! API error, retrying: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
            continue

        seen |= set(runs)
        discovering = time.time() < discovery_deadline
        tracked = want | seen

        missing = sorted(p for p in want if p not in runs)
        pending = sorted(p for p in tracked if p in runs and runs[p]["status"] != "completed")

        if not discovering and not missing and not pending:
            break

        state = "discovering" if discovering else "waiting"
        print(
            f"  [{state}] tracked={len(tracked)} missing={missing or '-'} "
            f"pending={pending or '-'}",
            flush=True,
        )
        time.sleep(POLL_SECONDS)

    print("\nResults:")
    failed, absent = [], []
    for path in sorted(want | seen):
        run = runs.get(path)
        if run is None:
            absent.append(path)
            print(f"  MISSING  {path}  (expected from the diff, never started)")
            continue
        concl = run.get("conclusion")
        ok = concl in PASSING
        if not ok:
            failed.append(f"{path} -> {concl}")
        status = "OK  " if ok else "FAIL"
        print(f"  {status}     {path}  [{run['name']}] {concl}  {run['html_url']}")

    if absent:
        print(f"\n::error::{len(absent)} expected workflow(s) never started: {', '.join(absent)}")
    if failed:
        print(f"\n::error::{len(failed)} workflow(s) failed: {', '.join(failed)}")
    if absent or failed:
        return 1

    print("\nAll component workflows relevant to this pull request are green.")
    return 0


def cmd_policy() -> int:
    """Routine CI must persist no Actions artifacts (docs/adr/0004-ci-artifact-policy.md)."""
    problems = []
    for path, wf in load_workflows().items():
        trig = triggers(wf)
        if "push" not in trig and "pull_request" not in trig:
            continue
        for job_name, job in (wf.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                if "actions/upload-artifact" in uses:
                    if "workflow_dispatch" not in str(step.get("if", "")):
                        problems.append(
                            f"{path}:{job_name}: upload-artifact without a "
                            "workflow_dispatch guard"
                        )
                if "docker/build-push-action" in uses:
                    env = {str(k): str(v) for k, v in (step.get("env") or {}).items()}
                    if env.get("DOCKER_BUILD_RECORD_UPLOAD", "").lower() != "false":
                        problems.append(
                            f"{path}:{job_name}: build-push-action without "
                            "DOCKER_BUILD_RECORD_UPLOAD: false"
                        )
    for p in problems:
        print(f"::error::{p}")
    if problems:
        return 1
    print("Artifact policy OK: no routine-CI workflow persists an artifact.")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "wait"
    sys.exit(cmd_policy() if mode == "policy" else cmd_wait())
