from __future__ import annotations

import hashlib
from pathlib import Path


DOWNLOADS_DIR = Path("openwrt-agent")
MANIFEST_FILE = "openwrt-agent-files.txt"
CHECKSUMS_FILE = "SHA256SUMS.txt"
SIGNATURE_FILE = "SHA256SUMS.sig"


def _sha256_for(path: Path) -> str:
    digest = hashlib.sha256()
    # Linux release jobs ship LF files. Canonicalizing text payloads keeps the
    # signed manifest identical when it is generated from a Windows checkout.
    digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def read_agent_version() -> str:
    source = (DOWNLOADS_DIR / "wrtmonitor-agent").read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith('AGENT_VERSION="') and line.endswith('"'):
            return line.split('"', 2)[1]
    raise RuntimeError("AGENT_VERSION not found in openwrt-agent/wrtmonitor-agent")


def manifest_entries() -> list[str]:
    manifest = (DOWNLOADS_DIR / MANIFEST_FILE).read_text(encoding="utf-8")
    return [
        line.strip()
        for line in manifest.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def ensure_openwrt_download_metadata() -> None:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    version = read_agent_version()
    with (DOWNLOADS_DIR / "agent-version.txt").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(f"{version}\n")
    checksums = []
    for filename in manifest_entries():
        if filename in {CHECKSUMS_FILE, SIGNATURE_FILE}:
            continue
        path = DOWNLOADS_DIR / filename
        checksums.append(f"{_sha256_for(path)}  {filename}")
    with (DOWNLOADS_DIR / CHECKSUMS_FILE).open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write("\n".join(checksums) + "\n")


def openwrt_download_metadata() -> dict[str, str | bool]:
    version = read_agent_version()
    return {
        "openwrt_downloads_enabled": True,
        "openwrt_agent_version": version,
        "openwrt_downloads_path": "/downloads/openwrt/",
    }
