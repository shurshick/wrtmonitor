"""Read-only gate before changing the container or GitHub latest pointers."""

import argparse
import json
import os
import re
import subprocess
from datetime import UTC, datetime


REQUIRED_JOBS = {
    "backend",
    "android",
    "android-emulator",
    "docker",
    "deployment-acceptance",
    "agent-release-metadata",
    "release-artifacts",
}


def github(path: str) -> dict:
    return json.loads(
        subprocess.check_output(["gh", "api", path], text=True, encoding="utf-8")
    )


def verify(repository: str, version: str, minimum_age_hours: int) -> dict[str, str]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected an exact numeric release version")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if not 0 <= minimum_age_hours <= 336:
        raise ValueError("Release age must be between 0 and 336 hours")
    prefix = f"repos/{repository}"
    tag = f"v{version}"
    release = github(f"{prefix}/releases/tags/{tag}")
    if release.get("draft") or release.get("tag_name") != tag:
        raise ValueError("Release must be published under the exact requested tag")
    published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    if (datetime.now(UTC) - published).total_seconds() < minimum_age_hours * 3600:
        raise ValueError("Release has not reached the required age")
    expected_assets = {
        "agent-version.txt",
        "SHA256SUMS.txt",
        "SHA256SUMS.sig",
        "SHA256SUMS.rsa.sig",
        f"wrtmonitor-android-v{version}.apk",
        f"wrtmonitor-openwrt-agent-v{version}.tar.gz",
        f"wrtmonitor-truenas-v{version}.yaml",
    }
    uploaded = {
        item["name"]
        for item in release.get("assets", [])
        if item.get("state") == "uploaded" and item.get("size", 0) > 0
    }
    if expected_assets - uploaded:
        raise ValueError(
            f"Missing release assets: {sorted(expected_assets - uploaded)}"
        )
    commit = github(f"{prefix}/commits/{tag}")["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid release commit")
    for workflow in ("ci.yml", "security.yml"):
        runs = github(
            f"{prefix}/actions/workflows/{workflow}/runs?head_sha={commit}&per_page=100"
        )["workflow_runs"]
        runs = [
            run
            for run in runs
            if run.get("head_sha") == commit
            and run.get("event") in {"push", "schedule", "workflow_dispatch"}
            and (workflow != "ci.yml" or run.get("head_branch") == tag)
        ]
        if not runs:
            raise ValueError(f"No trusted {workflow} run for release commit {commit}")
        run = max(runs, key=lambda item: item["id"])
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError(f"{workflow} has not passed for release commit {commit}")
        if workflow == "ci.yml":
            jobs = github(f"{prefix}/actions/runs/{run['id']}/jobs?per_page=100")[
                "jobs"
            ]
            passed = {job["name"] for job in jobs if job.get("conclusion") == "success"}
            if REQUIRED_JOBS - passed:
                raise ValueError(
                    f"Release jobs did not pass: {sorted(REQUIRED_JOBS - passed)}"
                )
    return {"tag": tag, "commit": commit}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--minimum-age-hours", type=int, default=0)
    args = parser.parse_args()
    result = verify(args.repository, args.version, args.minimum_age_hours)
    print(json.dumps(result))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            for key, value in result.items():
                stream.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
