from __future__ import annotations

from scripts.command_validation_report import new_report, validate


def test_new_hardware_report_is_not_certified() -> None:
    report = new_report("test-router")

    assert validate(report) == []
    assert {item["status"] for item in report["commands"].values()} == {"not_run"}


def test_pass_requires_evidence() -> None:
    report = new_report("test-router")
    command = next(iter(report["commands"].values()))
    command["status"] = "pass"

    assert any("PASS requires evidence" in error for error in validate(report))
