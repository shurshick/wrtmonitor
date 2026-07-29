from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "command-contract.json"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def new_report(router: str) -> dict:
    contract = load_contract()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "router": router,
        "contract_version": contract["command_contract_version"],
        "commands": {
            name: {
                "status": "not_run",
                "idempotency": "not_run",
                "timeout": "not_run",
                "redelivery": "not_run",
                "post_condition": "not_run",
                "rollback": "not_run",
                "evidence": None,
            }
            for name in contract["commands"]
        },
    }


def validate(report: dict) -> list[str]:
    expected = set(load_contract()["commands"])
    actual = set(report.get("commands") or {})
    errors: list[str] = []
    if missing := expected - actual:
        errors.append(f"missing commands: {sorted(missing)}")
    if unknown := actual - expected:
        errors.append(f"unknown commands: {sorted(unknown)}")
    allowed = {"not_run", "pass", "fail", "blocked", "not_applicable"}
    for name, result in (report.get("commands") or {}).items():
        for field in (
            "status",
            "idempotency",
            "timeout",
            "redelivery",
            "post_condition",
            "rollback",
        ):
            if result.get(field) not in allowed:
                errors.append(f"{name}: invalid {field}={result.get(field)!r}")
        if result.get("status") == "pass" and not result.get("evidence"):
            errors.append(f"{name}: PASS requires evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--router", default="physical-openwrt")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="fail unless every command has a final hardware result and evidence",
    )
    args = parser.parse_args()
    if args.init:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(new_report(args.router), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if not args.report.is_file():
        print(f"report not found: {args.report}")
        return 1
    report = json.loads(args.report.read_text(encoding="utf-8"))
    errors = validate(report)
    if args.require_complete:
        for name, result in report.get("commands", {}).items():
            if result.get("status") not in {"pass", "not_applicable"}:
                errors.append(f"{name}: hardware certification is incomplete")
            if result.get("status") == "pass" and not result.get("evidence"):
                errors.append(f"{name}: hardware certification has no evidence")
    if errors:
        print("\n".join(errors))
        return 1
    print("command validation report: valid; PASS entries require evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
