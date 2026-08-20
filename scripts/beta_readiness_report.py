from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MINIMUM_OBSERVATION_HOURS = 168
SAMPLING_TOLERANCE_HOURS = 2
REQUIRED_STANDS = {"Netis NX31", "OpenWrt x86"}
RUNTIME_PATHS = (
    "backend/app/**/*.py",
    "openwrt-agent/lib/*.sh",
    "openwrt-agent/wrtmonitor-agent",
)


def runtime_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        {
            path
            for pattern in RUNTIME_PATHS
            for path in root.glob(pattern)
            if path.is_file()
        },
        key=lambda path: path.as_posix(),
    )
    for path in files:
        # Git may check out text as LF or CRLF. Certification must describe the
        # runtime source, not the developer workstation's line-ending policy.
        content = path.read_bytes().replace(b"\r\n", b"\n")
        if path.name == "wrtmonitor-agent":
            content = re.sub(
                rb'^VERSION="[^"]+"$',
                b'VERSION="<release>"',
                content,
                flags=re.MULTILINE,
            )
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def api(server: str, path: str, *, token: str = "", body: dict | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(
        Request(server.rstrip("/") + path, data=payload, headers=headers), timeout=30
    ) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def stand_name(device: dict) -> str | None:
    text = " ".join(
        str(device.get(key) or "") for key in ("name", "hostname", "model")
    ).lower()
    if "netis" in text or "nx31" in text:
        return "Netis NX31"
    if "x86" in text or "virtualbox" in text:
        return "OpenWrt x86"
    return None


def build_stand(server: str, token: str, device: dict) -> dict:
    device_id = device["id"]
    history = api(
        server,
        f"/api/v1/devices/{device_id}/telemetry/history?{urlencode({'range': '7d', 'limit': 120})}",
        token=token,
    )
    points = history.get("points", history if isinstance(history, list) else [])
    times = sorted(parse_time(item["created_at"]) for item in points)
    if len(times) < 2:
        raise SystemExit(f"not enough telemetry points for {device['name']}")
    gaps = [
        (current - previous).total_seconds() / 60
        for previous, current in zip(times, times[1:])
    ]
    observed_hours = (times[-1] - times[0]).total_seconds() / 3600
    current_age = (datetime.now(UTC) - times[-1]).total_seconds()
    longest_gap = max(gaps)
    warnings = []
    if longest_gap > 60:
        warnings.append(
            f"stand recovered after a telemetry gap of {longest_gap:.1f} minutes"
        )
    passed = (
        observed_hours >= MINIMUM_OBSERVATION_HOURS - SAMPLING_TOLERANCE_HOURS
        and device.get("status") == "online"
        and current_age <= 300
    )
    return {
        "stand": stand_name(device),
        "device": device.get("name"),
        "status": device.get("status"),
        "requested_observation_hours": MINIMUM_OBSERVATION_HOURS,
        "observed_span_hours": round(observed_hours, 2),
        "sample_count": len(times),
        "first_sample_at": times[0].isoformat(),
        "last_sample_at": times[-1].isoformat(),
        "last_sample_age_seconds": round(current_age, 1),
        "median_gap_minutes": round(median(gaps), 1),
        "maximum_gap_minutes": round(longest_gap, 1),
        "recovered_after_longest_gap": times[-1] > times[0]
        and device.get("status") == "online",
        "warnings": warnings,
        "passed": passed,
    }


def collect(args: argparse.Namespace) -> None:
    username = args.username or os.environ.get("WRTMONITOR_BETA_USERNAME", "")
    password = os.environ.get("WRTMONITOR_BETA_PASSWORD", "")
    if not username or not password:
        raise SystemExit("set --username and WRTMONITOR_BETA_PASSWORD")
    tokens = api(
        args.server,
        "/api/v1/auth/login",
        body={"username": username, "password": password},
    )
    devices = api(args.server, "/api/v1/devices", token=tokens["access_token"])
    selected = [device for device in devices if stand_name(device)]
    stands = [
        build_stand(args.server, tokens["access_token"], device) for device in selected
    ]
    found = {item["stand"] for item in stands}
    report = {
        "schema_version": 1,
        "release_version": args.version,
        "generated_at": datetime.now(UTC).isoformat(),
        "observation_policy": {
            "minimum_hours": MINIMUM_OBSERVATION_HOURS,
            "sampling_tolerance_hours": SAMPLING_TOLERANCE_HOURS,
            "outages_are_reported_and_require_recovery": True,
        },
        "runtime_evidence": {
            "inherited_from": args.runtime_base,
            "reason": args.runtime_reason,
            "source_fingerprint_sha256": runtime_fingerprint(Path.cwd()),
        },
        "stands": stands,
        "checks": {
            "required_stands_present": found == REQUIRED_STANDS,
            "all_stands_online_and_fresh": all(item["passed"] for item in stands),
        },
    }
    report["status"] = "passed" if all(report["checks"].values()) else "failed"
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validate_report(report, args.version)
    print(args.output)


def validate_report(report: dict, version: str) -> None:
    if report.get("release_version") != version:
        raise SystemExit("beta-readiness report belongs to another release")
    if report.get("status") != "passed":
        raise SystemExit("beta-readiness report is not passed")
    if report.get("observation_policy", {}).get("minimum_hours", 0) < 168:
        raise SystemExit("beta-readiness observation is shorter than seven days")
    runtime_evidence = report.get("runtime_evidence", {})
    if not runtime_evidence.get("inherited_from") or not runtime_evidence.get("reason"):
        raise SystemExit("beta-readiness runtime fingerprint evidence is missing")
    expected_fingerprint = runtime_fingerprint(Path.cwd())
    if runtime_evidence.get("source_fingerprint_sha256") != expected_fingerprint:
        raise SystemExit("beta-readiness runtime fingerprint does not match source")
    stands = report.get("stands", [])
    if {item.get("stand") for item in stands} != REQUIRED_STANDS:
        raise SystemExit("beta-readiness report does not contain both required stands")
    for item in stands:
        if not item.get("passed"):
            raise SystemExit(f"stand is not accepted: {item.get('stand')}")
        if item.get("observed_span_hours", 0) < 166:
            raise SystemExit(f"stand observation is too short: {item.get('stand')}")


def validate(args: argparse.Namespace) -> None:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    validate_report(report, args.version)
    print(f"beta readiness accepted for {args.version}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--server", required=True)
    collect_parser.add_argument("--username")
    collect_parser.add_argument("--version", required=True)
    collect_parser.add_argument("--runtime-base", required=True)
    collect_parser.add_argument("--runtime-reason", required=True)
    collect_parser.add_argument("--output", required=True, type=Path)
    collect_parser.set_defaults(handler=collect)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("report", type=Path)
    validate_parser.add_argument("--version", required=True)
    validate_parser.set_defaults(handler=validate)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
