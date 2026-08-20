import json
from pathlib import Path

from scripts.runtime_validation_report import runtime_fingerprint, validate_report


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads(
    (ROOT / "contracts" / "command-contract.json").read_text(encoding="utf-8")
)


def test_runtime_report_requires_real_post_conditions(tmp_path: Path):
    evidence = tmp_path / "evidence"
    commands = {
        command: {"status": "not_applicable"} for command in CONTRACT["commands"]
    }
    for command, runtime in {
        "network.restart": {"fresh_telemetry": True, "ssh_reachable": True},
        "router.reboot": {"boot_id_changed": True, "fresh_telemetry": True},
        "agent.disconnect": {
            "disabled_observed": True,
            "daemon_stopped": True,
            "recovered": True,
        },
        "agent.update": {"actual_version": "0.49.0", "service_running": True},
        "agent.rollback": {"actual_version": "0.49.0", "service_running": True},
    }.items():
        path = evidence / command
        path.mkdir(parents=True)
        (path / "result.json").write_text(
            json.dumps({"runtime_post_condition": runtime}), encoding="utf-8"
        )
        commands[command] = {"status": "pass", "evidence": f"evidence/{command}"}
    terminal = evidence / "agent.ssh_session"
    terminal.mkdir(parents=True)
    (terminal / "result.json").write_text(
        json.dumps(
            {
                "input_confirmed": True,
                "resize_confirmed": True,
                "reconnect_confirmed": True,
                "close_confirmed": True,
            }
        ),
        encoding="utf-8",
    )
    commands["agent.ssh_session"] = {
        "status": "pass",
        "evidence": "evidence/agent.ssh_session",
    }
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"release_version": "0.49.0", "commands": commands}),
        encoding="utf-8",
    )

    assert validate_report(report, "0.49.0", tmp_path) == []

    payload = json.loads(
        (evidence / "router.reboot" / "result.json").read_text(encoding="utf-8")
    )
    payload["runtime_post_condition"]["boot_id_changed"] = False
    (evidence / "router.reboot" / "result.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    assert (
        "router.reboot: runtime post-condition boot_id_changed is missing"
        in validate_report(report, "0.49.0", tmp_path)
    )


def test_runtime_report_rejects_incomplete_contract_and_wrong_update_version(
    tmp_path: Path,
):
    evidence = tmp_path / "evidence" / "agent.update"
    evidence.mkdir(parents=True)
    (evidence / "result.json").write_text(
        json.dumps(
            {
                "runtime_post_condition": {
                    "actual_version": "0.48.0",
                    "service_running": True,
                }
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "release_version": "0.49.0",
                "commands": {
                    "agent.update": {
                        "status": "pass",
                        "evidence": "evidence/agent.update",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    failures = validate_report(report, "0.49.0", tmp_path)
    assert any(failure.startswith("commands are missing:") for failure in failures)
    assert (
        "agent.update: actual version is '0.48.0', expected certified version '0.49.0'"
        in failures
    )


def test_runtime_report_can_be_inherited_only_for_identical_runtime(tmp_path: Path):
    agent_root = tmp_path / "openwrt-agent"
    agent_root.mkdir()
    (agent_root / "openwrt-agent-files.txt").write_text(
        "wrtmonitor-agent\nagent-version.txt\nSHA256SUMS.txt\nlib/runtime.sh\n",
        encoding="utf-8",
    )
    (agent_root / "wrtmonitor-agent").write_text(
        '#!/bin/sh\nAGENT_VERSION="0.50.0"\n', encoding="utf-8"
    )
    (agent_root / "agent-version.txt").write_text("0.50.0\n", encoding="utf-8")
    (agent_root / "SHA256SUMS.txt").write_text("release metadata\n", encoding="utf-8")
    (agent_root / "lib").mkdir()
    (agent_root / "lib" / "runtime.sh").write_text("run_command\n", encoding="utf-8")

    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "release_version": "0.49.0",
                "runtime_fingerprint": runtime_fingerprint(tmp_path),
                "commands": {},
            }
        ),
        encoding="utf-8",
    )

    failures = validate_report(report, "0.50.0", tmp_path)
    assert not any("certified runtime fingerprint" in failure for failure in failures)

    (agent_root / "lib" / "runtime.sh").write_text(
        "changed_command\n", encoding="utf-8"
    )
    failures = validate_report(report, "0.50.0", tmp_path)
    assert any("certified runtime fingerprint" in failure for failure in failures)
