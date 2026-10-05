import json

import pytest

from scripts import verify_release_readiness as gate


@pytest.fixture
def exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "runtime_fingerprint", lambda root: "fingerprint")
    directory = tmp_path / "certification"
    directory.mkdir()
    path = directory / "release-exception-v0.55.3.json"
    data = {
        "release_version": "0.55.3",
        "scope": "long_running_hardware_soak_only",
        "approved_by": "project_owner",
        "approval": "Explicit owner approval",
        "reason": "Release without new soak",
        "source_fingerprint_sha256": "fingerprint",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_explicit_exception_is_not_reported_as_certification(exception):
    assert "soak NOT RUN" in gate.verify("0.55.3")


@pytest.mark.parametrize(
    "field",
    [
        "release_version",
        "scope",
        "approved_by",
        "approval",
        "reason",
        "source_fingerprint_sha256",
    ],
)
def test_invalid_exception_fails_closed(exception, field):
    path, data = exception
    data[field] = ""
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        gate.verify("0.55.3")


def test_exception_does_not_apply_to_next_release(exception):
    with pytest.raises(FileNotFoundError):
        gate.verify("0.55.4")


def test_regular_release_still_validates_report(exception, monkeypatch):
    path, _ = exception
    path.unlink()
    report = path.parent / "beta-readiness-v0.55.3.json"
    report.write_text('{"status": "failed"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        gate.verify("0.55.3")


def test_stable_release_cannot_use_testing_exception(exception):
    path, data = exception
    data["release_version"] = "1.0.0"
    (path.parent / "release-exception-v1.0.0.json").write_text(json.dumps(data))
    with pytest.raises(FileNotFoundError, match="stable-readiness"):
        gate.verify("1.0.0")


def test_stable_requires_license_and_explicit_decision(exception):
    path, _ = exception
    decision = path.parent / "stable-readiness-v1.0.0.json"
    decision.write_text(json.dumps({"release_version": "1.0.0", "decision": "testing"}))
    with pytest.raises(ValueError, match="LICENSE"):
        gate.verify("1.0.0")
    (path.parent.parent / "LICENSE").write_text("Owner-selected license")
    with pytest.raises(ValueError, match="decision"):
        gate.verify("1.0.0")


def test_stable_requires_real_hardware_not_empty_list(exception):
    path, _ = exception
    (path.parent.parent / "LICENSE").write_text("Owner-selected license")
    (path.parent / "stable-readiness-v1.0.0.json").write_text(
        json.dumps(
            {
                "release_version": "1.0.0",
                "decision": "release",
                "approved_by": "project_owner",
                "source_fingerprint_sha256": "fingerprint",
                "hardware_reports": [],
            }
        )
    )
    with pytest.raises(ValueError, match="physical"):
        gate.verify("1.0.0")


@pytest.mark.parametrize(
    "hardware_kind,server_version,validation_result,accepted",
    [
        ("physical_router", "1.0.0", 0, True),
        ("virtual_machine", "1.0.0", 0, False),
        ("physical_router", "0.55.5", 0, False),
        ("physical_router", "1.0.0", 1, False),
    ],
)
def test_stable_checks_candidate_and_full_validation(
    exception, monkeypatch, hardware_kind, server_version, validation_result, accepted
):
    from scripts import runtime_validation_report as hardware

    path, _ = exception
    (path.parent.parent / "LICENSE").write_text("Owner-selected license")
    monkeypatch.setattr(
        hardware, "runtime_fingerprint", lambda root: "agent-fingerprint"
    )
    monkeypatch.setattr(
        hardware, "validate_report", lambda *args, **kwargs: validation_result
    )
    (path.parent / "candidate.json").write_text(
        json.dumps(
            {
                "hardware_kind": hardware_kind,
                "release_version": "1.0.0",
                "server_version": server_version,
                "runtime_fingerprint": "agent-fingerprint",
            }
        )
    )
    (path.parent / "stable-readiness-v1.0.0.json").write_text(
        json.dumps(
            {
                "release_version": "1.0.0",
                "decision": "release",
                "approved_by": "project_owner",
                "source_fingerprint_sha256": "fingerprint",
                "hardware_reports": ["certification/candidate.json"],
            }
        )
    )
    if accepted:
        assert "accepted" in gate.verify("1.0.0")
    else:
        with pytest.raises(ValueError):
            gate.verify("1.0.0")
