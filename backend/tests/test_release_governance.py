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
