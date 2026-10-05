"""Build a flat, verifiable inventory of every downloaded release asset."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def build_inventory(
    root: Path, output: Path, version: str, commit: str, image_digest: str
) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid version")
    if (root / "VERSION").read_text().strip() != version:
        raise ValueError("Version differs from source")
    if (root / "RELEASE_TAG").read_text().strip() != f"v{version}":
        raise ValueError("Release tag differs from version")
    if (root / "openwrt-agent/agent-version.txt").read_text().strip() != version:
        raise ValueError("Agent version differs from release")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", image_digest
    ):
        raise ValueError("Invalid commit or image digest")
    files = [
        root / f"wrtmonitor-{kind}-v{version}.{suffix}"
        for kind, suffix in (
            ("android", "apk"),
            ("openwrt-agent", "tar.gz"),
            ("truenas", "yaml"),
        )
    ]
    files += [
        root / "openwrt-agent" / name
        for name in (
            "agent-version.txt",
            "SHA256SUMS.txt",
            "SHA256SUMS.sig",
            "SHA256SUMS.rsa.sig",
        )
    ]
    for path in files:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty release asset: {path.name}")
    output.mkdir(parents=True, exist_ok=True)
    metadata = output / "RELEASE_INVENTORY.json"
    metadata.write_text(
        json.dumps(
            {
                "schema": "wrtmonitor.release-inventory.v1",
                "version": version,
                "tag": f"v{version}",
                "commit": commit,
                "image": "ghcr.io/shurshick/wrtmonitor",
                "image_digest": image_digest,
                "assets": [path.name for path in files],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    files.append(metadata)
    (output / "RELEASE_SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("."))
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--image-digest", required=True)
    args = parser.parse_args()
    build_inventory(
        args.root, args.output, args.version, args.commit, args.image_digest
    )


if __name__ == "__main__":
    main()
