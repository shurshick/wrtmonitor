#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def version_code_at(ref: str) -> int:
    value = subprocess.check_output(
        ["git", "show", f"{ref}:VERSION_CODE"], cwd=ROOT, text=True
    ).strip()
    return int(value)


def validate(previous_ref: str | None = None) -> None:
    version = read_text(ROOT / "VERSION")
    release_tag = read_text(ROOT / "RELEASE_TAG")
    version_code = int(read_text(ROOT / "VERSION_CODE"))
    agent_version = read_text(ROOT / "openwrt-agent" / "agent-version.txt")
    agent_source = read_text(ROOT / "openwrt-agent" / "wrtmonitor-agent")

    if release_tag != f"v{version}":
        raise ValueError(
            f"RELEASE_TAG {release_tag!r} does not match VERSION {version!r}"
        )
    if agent_version != version:
        raise ValueError("agent-version.txt does not match VERSION")
    if f'AGENT_VERSION="{version}"' not in agent_source:
        raise ValueError("wrtmonitor-agent AGENT_VERSION does not match VERSION")
    if version_code <= 0:
        raise ValueError("VERSION_CODE must be positive")

    if previous_ref:
        previous_code = version_code_at(previous_ref)
        if version_code <= previous_code:
            raise ValueError(
                f"VERSION_CODE must increase: current={version_code}, "
                f"{previous_ref}={previous_code}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate release metadata")
    parser.add_argument("--previous-ref")
    args = parser.parse_args()
    validate(args.previous_ref)
    print("Release metadata is consistent and VERSION_CODE is monotonic.")


if __name__ == "__main__":
    main()
