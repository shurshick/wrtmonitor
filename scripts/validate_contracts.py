from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
AGENT_COMPATIBILITY_ALIASES = {"dns.install_encrypted", "dns.set_encrypted"}
sys.path.insert(0, str(ROOT))

from backend.app.contracts import (  # noqa: E402
    COMMAND_CONTRACT_VERSION,
    TELEMETRY_SCHEMA_CURRENT,
)
from backend.app.services.command_registry import COMMAND_REGISTRY  # noqa: E402


def agent_commands() -> set[str]:
    source = (ROOT / "openwrt-agent/lib/commands.sh").read_text(encoding="utf-8")
    body = source[source.index("execute_command() {") :]
    groups = re.findall(r"^        ([a-z][a-z0-9_.|]+)\)$", body, re.MULTILINE)
    return {item for group in groups for item in group.split("|")}


def agent_capabilities() -> set[str]:
    source = (ROOT / "openwrt-agent/lib/capabilities.sh").read_text(encoding="utf-8")
    body = source[
        source.index("capability_keys()") : source.index("capability_supported()")
    ]
    return set(re.findall(r"[a-z][a-z0-9_.]+", body))


def manifest() -> dict:
    return {
        "command_contract_version": COMMAND_CONTRACT_VERSION,
        "telemetry_schema_version": TELEMETRY_SCHEMA_CURRENT,
        "commands": {key: COMMAND_REGISTRY[key] for key in sorted(COMMAND_REGISTRY)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected_commands = set(COMMAND_REGISTRY)
    dispatched = agent_commands()
    missing_dispatch = expected_commands - dispatched
    unknown_dispatch = dispatched - expected_commands - AGENT_COMPATIBILITY_ALIASES
    capabilities = agent_capabilities()
    missing_capabilities = {
        item["capability"]
        for item in COMMAND_REGISTRY.values()
        if item.get("capability") not in capabilities
    }
    errors = []
    reliability_fields = {
        "subsystem",
        "idempotency",
        "delivery",
        "post_condition",
        "rollback",
        "verification",
    }
    incomplete_reliability = {
        command
        for command, metadata in COMMAND_REGISTRY.items()
        if reliability_fields - set(metadata.get("reliability", {}))
    }
    if missing_dispatch:
        errors.append(f"agent misses commands: {sorted(missing_dispatch)}")
    if unknown_dispatch:
        errors.append(f"agent exposes unknown commands: {sorted(unknown_dispatch)}")
    if missing_capabilities:
        errors.append(f"agent misses capabilities: {sorted(missing_capabilities)}")
    if incomplete_reliability:
        errors.append(
            f"commands miss reliability policy: {sorted(incomplete_reliability)}"
        )
    non_fail_closed = {
        command
        for command, metadata in COMMAND_REGISTRY.items()
        if metadata.get("reliability", {}).get("verification", {}).get("fail_closed")
        is not True
    }
    if non_fail_closed:
        errors.append(
            f"commands do not fail closed during verification: {sorted(non_fail_closed)}"
        )

    target = ROOT / "contracts/command-contract.json"
    rendered = json.dumps(manifest(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    elif not target.is_file() or target.read_text(encoding="utf-8") != rendered:
        errors.append("contracts/command-contract.json is stale; run with --write")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"contract OK: {len(expected_commands)} commands, "
        f"command v{COMMAND_CONTRACT_VERSION}, telemetry v{TELEMETRY_SCHEMA_CURRENT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
