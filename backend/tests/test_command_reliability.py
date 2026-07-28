from backend.app.services.command_registry import COMMAND_REGISTRY
from backend.app.services.command_reliability import command_subsystem
from backend.app.services.command_errors import public_command_error


def test_all_commands_have_executable_reliability_policy():
    assert len(COMMAND_REGISTRY) == 80
    for command_type, metadata in COMMAND_REGISTRY.items():
        policy = metadata["reliability"]
        assert policy["subsystem"] == command_subsystem(command_type)
        assert policy["idempotency"]["strategy"] == "command_uuid_result_cache"
        assert policy["delivery"]["timeout_seconds"] >= 30
        assert policy["delivery"]["max_deliveries"] in {2, 3}
        assert policy["post_condition"]
        assert policy["rollback"]


def test_disruptive_commands_have_longer_timeout_and_explicit_rollback():
    disruptive = {
        name: item
        for name, item in COMMAND_REGISTRY.items()
        if item["risk_level"] == "level_4_disruptive"
    }
    assert disruptive
    for metadata in disruptive.values():
        policy = metadata["reliability"]
        assert policy["delivery"]["timeout_seconds"] >= 300
        assert policy["rollback"] != "not_required"


def test_structured_agent_error_has_actionable_public_reason():
    error = public_command_error(
        {
            "error": "wifi radio not found",
            "error_detail": {
                "code": "resource_unavailable",
                "message": "wifi radio not found",
                "retryable": False,
            },
        }
    )
    assert error == {
        "code": "resource_unavailable",
        "title": "Нужный компонент недоступен",
        "message": "wifi radio not found",
        "retryable": False,
    }
