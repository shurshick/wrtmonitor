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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(verify(args.version))


if __name__ == "__main__":
    main()
