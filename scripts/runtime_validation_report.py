from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "command-contract.json"
REQUIRED_RUNTIME = {
    "network.restart": ("fresh_telemetry", "ssh_reachable"),
    "router.reboot": ("boot_id_changed", "fresh_telemetry"),
    "agent.disconnect": ("disabled_observed", "daemon_stopped", "recovered"),
    "agent.update": ("actual_version", "service_running"),
    "agent.rollback": ("actual_version", "service_running"),
}
RUNTIME_MANIFEST = "openwrt-agent/openwrt-agent-files.txt"
FINGERPRINT_EXCLUDED = {"agent-version.txt", "SHA256SUMS.txt"}


def runtime_fingerprint(root: Path = ROOT) -> str:
    agent_root = root / "openwrt-agent"
    names = (root / RUNTIME_MANIFEST).read_text(encoding="utf-8").splitlines()
    digest = hashlib.sha256()
    for name in sorted(name.strip() for name in names if name.strip()):
        if name in FINGERPRINT_EXCLUDED:
            continue
        content = (agent_root / name).read_bytes()
        if name == "wrtmonitor-agent":
            text = content.decode("utf-8")
            text = re.sub(
                r'^AGENT_VERSION="[^"]+"$',
                'AGENT_VERSION="<release>"',
                text,
                flags=re.MULTILINE,
            )
            content = text.encode("utf-8")
        digest.update(name.encode("utf-8") + b"\0" + content + b"\0")
    return digest.hexdigest()


def load_evidence(root: Path, reference: str) -> dict[str, Any]:
    return json.loads((root / reference / "result.json").read_text(encoding="utf-8"))


def validate_report(path: Path, expected_version: str, root: Path = ROOT) -> list[str]:
    report = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected_commands = set(contract["commands"])
    actual_commands = set(report.get("commands", {}))
    certified_version = report.get("release_version")
    if certified_version != expected_version:
        fingerprint = report.get("runtime_fingerprint")
        current_fingerprint = runtime_fingerprint(root)
        if fingerprint != current_fingerprint:
            failures.append(
                f"release version is {certified_version!r}, expected {expected_version!r}, "
                "and the certified runtime fingerprint does not match"
            )
    missing_commands = sorted(expected_commands - actual_commands)
    unexpected_commands = sorted(actual_commands - expected_commands)
    if missing_commands:
        failures.append(f"commands are missing: {', '.join(missing_commands)}")
    if unexpected_commands:
        failures.append(f"unexpected commands: {', '.join(unexpected_commands)}")
    for command, result in report.get("commands", {}).items():
        if result.get("status") not in {"pass", "not_applicable"}:
            failures.append(f"{command}: status={result.get('status')}")
    for command, fields in REQUIRED_RUNTIME.items():
        result = report.get("commands", {}).get(command) or {}
        reference = result.get("evidence")
        if not reference:
            failures.append(f"{command}: evidence is missing")
            continue
        runtime = load_evidence(root, reference).get("runtime_post_condition") or {}
        for field in fields:
            if not runtime.get(field):
                failures.append(f"{command}: runtime post-condition {field} is missing")
        if (
            command == "agent.update"
            and runtime.get("actual_version") != certified_version
        ):
            failures.append(
                f"agent.update: actual version is {runtime.get('actual_version')!r}, "
                f"expected certified version {certified_version!r}"
            )
    terminal = report.get("commands", {}).get("agent.ssh_session") or {}
    reference = terminal.get("evidence")
    if not reference:
        failures.append("agent.ssh_session: evidence is missing")
    else:
        evidence = load_evidence(root, reference)
        for field in (
            "input_confirmed",
            "resize_confirmed",
            "reconnect_confirmed",
            "close_confirmed",
        ):
            if not evidence.get(field):
                failures.append(f"agent.ssh_session: {field} is missing")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate runtime hardware evidence")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument(
        "--expected-version",
        default=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    )
    args = parser.parse_args()
    failures: list[str] = []
    for report in args.reports:
        failures.extend(
            f"{report}: {failure}"
            for failure in validate_report(report, args.expected_version)
        )
    if failures:
        print("runtime certification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Runtime certification passed for {len(args.reports)} hardware reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
