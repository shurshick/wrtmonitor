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
