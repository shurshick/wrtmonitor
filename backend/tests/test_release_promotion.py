from datetime import UTC, datetime, timedelta

import pytest

from scripts import verify_release_promotion as gate


@pytest.fixture
def responses(monkeypatch):
    sha = "a" * 40
    assets = [
        "agent-version.txt",
        "SHA256SUMS.txt",
        "SHA256SUMS.sig",
        "SHA256SUMS.rsa.sig",
        "wrtmonitor-android-v1.0.0.apk",
        "wrtmonitor-openwrt-agent-v1.0.0.tar.gz",
        "wrtmonitor-truenas-v1.0.0.yaml",
    ]
    release = {
        "tag_name": "v1.0.0",
        "draft": False,
        "published_at": (datetime.now(UTC) - timedelta(hours=72)).isoformat(),
        "assets": [{"name": name, "state": "uploaded", "size": 10} for name in assets],
    }
    run = {
        "id": 42,
        "head_sha": sha,
        "head_branch": "v1.0.0",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
    }
    data = {
        "releases/tags/v1.0.0": release,
        "commits/v1.0.0": {"sha": sha},
        f"actions/workflows/ci.yml/runs?head_sha={sha}&per_page=100": {
            "workflow_runs": [dict(run)]
        },
        f"actions/workflows/security.yml/runs?head_sha={sha}&per_page=100": {
            "workflow_runs": [dict(run)]
        },
        "actions/runs/42/jobs?per_page=100": {
            "jobs": [
                {"name": name, "conclusion": "success"} for name in gate.REQUIRED_JOBS
            ]
        },
    }
    monkeypatch.setattr(
        gate, "github", lambda path: data[path.removeprefix("repos/owner/repo/")]
    )
    return data


def test_exact_successful_release_is_accepted(responses):
    assert gate.verify("owner/repo", "1.0.0", 24) == {
        "tag": "v1.0.0",
        "commit": "a" * 40,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("head_sha", "b" * 40),
        ("event", "pull_request"),
        ("head_branch", "main"),
        ("conclusion", "failure"),
        ("status", "in_progress"),
    ],
)
def test_unrelated_failed_or_running_ci_is_rejected(responses, field, value):
    responses[f"actions/workflows/ci.yml/runs?head_sha={'a' * 40}&per_page=100"][
        "workflow_runs"
    ][0][field] = value
    with pytest.raises(ValueError):
        gate.verify("owner/repo", "1.0.0", 0)


def test_newer_failure_cannot_hide_behind_old_success(responses):
    runs = responses[f"actions/workflows/ci.yml/runs?head_sha={'a' * 40}&per_page=100"][
        "workflow_runs"
    ]
    runs.append({**runs[0], "id": 43, "conclusion": "failure"})
    with pytest.raises(ValueError):
        gate.verify("owner/repo", "1.0.0", 0)


def test_skipped_release_job_is_rejected(responses):
    responses["actions/runs/42/jobs?per_page=100"]["jobs"][0]["conclusion"] = "skipped"
    with pytest.raises(ValueError, match="Release jobs"):
        gate.verify("owner/repo", "1.0.0", 0)


def test_missing_artifact_is_rejected(responses):
    responses["releases/tags/v1.0.0"]["assets"].pop()
    with pytest.raises(ValueError, match="Missing release assets"):
        gate.verify("owner/repo", "1.0.0", 0)


def test_failed_security_run_is_rejected(responses):
    responses[f"actions/workflows/security.yml/runs?head_sha={'a' * 40}&per_page=100"][
        "workflow_runs"
    ][0]["conclusion"] = "failure"
    with pytest.raises(ValueError, match="security.yml"):
        gate.verify("owner/repo", "1.0.0", 0)


@pytest.mark.parametrize("draft,age", [(True, 0), (False, 100)])
def test_draft_or_young_release_is_rejected(responses, draft, age):
    responses["releases/tags/v1.0.0"]["draft"] = draft
    with pytest.raises(ValueError):
        gate.verify("owner/repo", "1.0.0", age)


@pytest.mark.parametrize(
    "version", ["1.0.0-rc1", "1.0.0;echo bad", "../main", "latest"]
)
def test_version_requires_exact_numeric_tag(version):
    with pytest.raises(ValueError):
        gate.verify("owner/repo", version, 0)
