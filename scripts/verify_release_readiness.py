#!/usr/bin/env python3
"""Accept real soak evidence or a source-bound, explicit release exception."""

import argparse
import json
import re
from pathlib import Path

try:
    from scripts.beta_readiness_report import runtime_fingerprint, validate_report
except ModuleNotFoundError:
    from beta_readiness_report import runtime_fingerprint, validate_report


def verify(version: str) -> str:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected numeric release version")
    if int(version.split(".")[0]) >= 1:
        return verify_stable(version)
    exception = Path(f"certification/release-exception-v{version}.json")
    if exception.exists():
        data = json.loads(exception.read_text(encoding="utf-8"))
        if (
            data.get("release_version") != version
            or data.get("scope") != "long_running_hardware_soak_only"
            or data.get("approved_by") != "project_owner"
            or not data.get("approval")
            or not data.get("reason")
            or data.get("source_fingerprint_sha256") != runtime_fingerprint(Path.cwd())
        ):
            raise ValueError("Invalid or stale release exception")
        return f"NOTICE: {version} soak NOT RUN; explicitly waived by project owner"
    report = json.loads(
        Path(f"certification/beta-readiness-v{version}.json").read_text(
            encoding="utf-8"
        )
    )
    validate_report(report, version)
    return f"Soak evidence accepted for {version}"


def verify_stable(version: str) -> str:
    try:
        from scripts.runtime_validation_report import (
            runtime_fingerprint as agent_fingerprint,
            validate_report as validate_hardware,
        )
    except ModuleNotFoundError:
        from runtime_validation_report import (
            runtime_fingerprint as agent_fingerprint,
            validate_report as validate_hardware,
        )

    root = Path.cwd()
    decision = json.loads(
        (root / f"certification/stable-readiness-v{version}.json").read_text(
            encoding="utf-8"
        )
    )
    if not (root / "LICENSE").is_file():
        raise ValueError("Stable release requires owner-approved LICENSE")
    if (
        decision.get("release_version") != version
        or decision.get("approved_by") != "project_owner"
        or decision.get("decision") != "release"
        or decision.get("source_fingerprint_sha256") != runtime_fingerprint(root)
    ):
        raise ValueError("Missing or stale stable release decision")
    reports = decision.get("hardware_reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("Stable release requires a full physical hardware E2E")
    for reference in reports:
        path = (root / reference).resolve()
        if not path.is_relative_to((root / "certification").resolve()):
            raise ValueError("Hardware report must be inside certification")
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report.get("hardware_kind") != "physical_router"
            or report.get("release_version") != version
            or report.get("server_version") != version
            or report.get("runtime_fingerprint") != agent_fingerprint(root)
        ):
            raise ValueError(
                "Stable hardware evidence must cover the exact physical candidate"
            )
        if validate_hardware(path, version, root, require_lifecycle=True):
            raise ValueError("Stable hardware E2E has not passed")
    return f"Owner decision and physical hardware E2E accepted for {version}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(verify(args.version))


if __name__ == "__main__":
    main()
