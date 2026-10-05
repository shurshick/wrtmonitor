import hashlib
import json
import subprocess

import pytest

from scripts.release_inventory import build_inventory


@pytest.fixture
def release_tree(tmp_path):
    (tmp_path / "openwrt-agent").mkdir()
    (tmp_path / "VERSION").write_text("1.0.0\n")
    (tmp_path / "RELEASE_TAG").write_text("v1.0.0\n")
    (tmp_path / "LICENSE").write_text("Apache License, Version 2.0\n")
    for name in (
        "agent-version.txt",
        "SHA256SUMS.txt",
        "SHA256SUMS.sig",
        "SHA256SUMS.rsa.sig",
    ):
        (tmp_path / "openwrt-agent" / name).write_text("1.0.0\n")
    for name in (
        "wrtmonitor-android-v1.0.0.apk",
        "wrtmonitor-openwrt-agent-v1.0.0.tar.gz",
        "wrtmonitor-truenas-v1.0.0.yaml",
    ):
        (tmp_path / name).write_bytes(b"test-release-asset")
    return tmp_path


def test_inventory_covers_every_asset_and_container_digest(release_tree):
    build_inventory(release_tree, release_tree, "1.0.0", "a" * 40, "sha256:" + "b" * 64)
    manifest = (release_tree / "RELEASE_SHA256SUMS.txt").read_text().splitlines()
    assert len(manifest) == 9
    for line in manifest:
        digest, name = line.split("  ")
        path = release_tree / name
        if not path.is_file():
            path = release_tree / "openwrt-agent" / name
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = json.loads((release_tree / "RELEASE_INVENTORY.json").read_text())
    assert metadata["tag"] == "v1.0.0"
    assert metadata["image_digest"] == "sha256:" + "b" * 64


def test_inventory_rejects_mixed_agent_versions(release_tree):
    (release_tree / "openwrt-agent/agent-version.txt").write_text("0.55.5")
    with pytest.raises(ValueError, match="Agent version"):
        build_inventory(
            release_tree, release_tree, "1.0.0", "a" * 40, "sha256:" + "b" * 64
        )


def test_inventory_rejects_missing_asset(release_tree):
    (release_tree / "wrtmonitor-android-v1.0.0.apk").unlink()
    with pytest.raises(ValueError, match="Missing"):
        build_inventory(
            release_tree, release_tree, "1.0.0", "a" * 40, "sha256:" + "b" * 64
        )


@pytest.mark.parametrize("algorithm", ["ED25519", "RSA"])
def test_inventory_signature_dry_run_and_tamper_rejection(release_tree, algorithm):
    build_inventory(release_tree, release_tree, "1.0.0", "a" * 40, "sha256:" + "b" * 64)
    private = release_tree / "private.pem"
    public = release_tree / "public.pem"
    signature = release_tree / "inventory.sig"
    manifest = release_tree / "RELEASE_SHA256SUMS.txt"

    def run(*args, check=True):
        return subprocess.run(
            ["openssl", *map(str, args)], capture_output=True, check=check
        )

    run("genpkey", "-algorithm", algorithm, "-out", private)
    run("pkey", "-in", private, "-pubout", "-out", public)
    if algorithm == "ED25519":
        run(
            "pkeyutl",
            "-sign",
            "-inkey",
            private,
            "-rawin",
            "-in",
            manifest,
            "-out",
            signature,
        )
        verify = [
            "pkeyutl",
            "-verify",
            "-pubin",
            "-inkey",
            public,
            "-rawin",
            "-in",
            manifest,
            "-sigfile",
            signature,
        ]
    else:
        run("dgst", "-sha256", "-sign", private, "-out", signature, manifest)
        verify = [
            "dgst",
            "-sha256",
            "-verify",
            public,
            "-signature",
            signature,
            manifest,
        ]
    run(*verify)
    manifest.write_text(manifest.read_text() + "tampered\n")
    assert run(*verify, check=False).returncode != 0
