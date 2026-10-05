from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_apache_license_is_included_in_agent_and_android():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Version 2.0, January 2004" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
    for path in ("openwrt-agent/LICENSE", "android/app/src/main/assets/LICENSE"):
        assert (ROOT / path).read_text(encoding="utf-8") == license_text
    assert (
        "LICENSE"
        in (ROOT / "openwrt-agent/openwrt-agent-files.txt").read_text().splitlines()
    )
