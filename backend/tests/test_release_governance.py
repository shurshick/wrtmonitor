from pathlib import Path

import pytest

from scripts.validate_release_metadata import validate

ROOT = Path(__file__).resolve().parents[2]


def test_current_release_metadata_is_consistent():
    validate()


def test_version_code_is_higher_than_previous_release(
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import validate_release_metadata as metadata

    monkeypatch.setattr(metadata, "version_code_at", lambda _ref: 87)
    monkeypatch.setattr(metadata, "release_tag_at", lambda _ref: "v0.45.0")
    validate("previous-release")


def test_version_code_may_stay_equal_for_followup_commit_in_same_release(
    monkeypatch: pytest.MonkeyPatch,
):
    from scripts import validate_release_metadata as metadata

    current_code = int((ROOT / "VERSION_CODE").read_text().strip())
    current_tag = (ROOT / "RELEASE_TAG").read_text().strip()
    monkeypatch.setattr(metadata, "version_code_at", lambda _ref: current_code)
    monkeypatch.setattr(metadata, "release_tag_at", lambda _ref: current_tag)
    validate("current-release")


def test_version_code_must_increase_for_new_release(monkeypatch: pytest.MonkeyPatch):
    from scripts import validate_release_metadata as metadata

    current_code = int((ROOT / "VERSION_CODE").read_text().strip())
    monkeypatch.setattr(metadata, "version_code_at", lambda _ref: current_code)
    monkeypatch.setattr(metadata, "release_tag_at", lambda _ref: "v0.0.0")
    with pytest.raises(ValueError, match="must not decrease"):
        validate("previous-release")


def test_legacy_and_current_rsa_keys_are_distinct():
    current = (ROOT / "openwrt-agent" / "update-rsa-public-key.pem").read_bytes()
    legacy = (ROOT / "openwrt-agent" / "update-rsa-legacy-public-key.pem").read_bytes()
    assert current != legacy


def test_release_tag_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch):
    from scripts import validate_release_metadata as metadata

    original = metadata.read_text

    def mismatched(path: Path) -> str:
        if path.name == "RELEASE_TAG":
            return "v0.0.0"
        return original(path)

    monkeypatch.setattr(metadata, "read_text", mismatched)
    with pytest.raises(ValueError, match="does not match"):
        metadata.validate()


def test_web_ssh_cache_key_tracks_server_version():
    template = (
        ROOT / "backend" / "app" / "templates" / "partials" / "ssh.html"
    ).read_text(encoding="utf-8")
    assert "web-ssh.js?v={{ server_version }}" in template


def test_beta_readiness_fingerprint_ignores_platform_line_endings(tmp_path: Path):
    from scripts.beta_readiness_report import runtime_fingerprint

    backend = tmp_path / "backend" / "app"
    backend.mkdir(parents=True)
    source = backend / "runtime.py"
    source.write_bytes(b"first\nsecond\n")
    lf_fingerprint = runtime_fingerprint(tmp_path)

    source.write_bytes(b"first\r\nsecond\r\n")

    assert runtime_fingerprint(tmp_path) == lf_fingerprint
