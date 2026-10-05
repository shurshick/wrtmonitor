from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

from backend.app.services.agent_versions import (
    agent_update_view,
    with_agent_update_view,
)


@pytest.mark.parametrize(
    "installed,source,state,available",
    [
        ("1.0.0", "0.55.5", "source_older", None),
        ("1.0.0", "1.0.0", "current", None),
        ("1.0.0", "1.0.1", "available", "1.0.1"),
        ("1.0.0-rc1", "1.0.0", "available", "1.0.0"),
        ("1.0.0", "1.0.0-rc1", "source_older", None),
        ("development", "1.0.0", "unknown", None),
        ("1.0.0", "", "unknown", None),
    ],
)
def test_only_newer_verified_source_is_an_update(installed, source, state, available):
    raw = {"version": installed, "available_version": source}
    enriched = with_agent_update_view(raw)
    assert enriched["available_version"] == source
    assert enriched["update_view"]["state"] == state
    assert enriched["update_view"]["available_version"] == available
    assert raw == {"version": installed, "available_version": source}


def test_legacy_downgrade_is_not_a_failure_but_real_errors_stay_visible():
    raw = {
        "version": "1.0.0",
        "available_version": "0.55.5",
        "last_update_status": "skipped",
        "last_update_error": "downgrade blocked",
    }
    assert agent_update_view(raw)["error"] is None
    assert raw["last_update_error"] == "downgrade blocked"
    for error in ("download failed", "checksum or syntax verification failed"):
        raw.update(last_update_status="failed", last_update_error=error)
        view = agent_update_view(raw)
        assert view["state"] == "error"
        assert view["error"] == error
        assert view["available_version"] is None


def render_agent(agent, server_version="1.0.0"):
    environment = Environment(
        loader=FileSystemLoader("backend/app/templates"), autoescape=True
    )
    environment.filters["timestamp"] = str
    return environment.get_template("partials/agent.html").render(
        agent={**agent, "update_view": agent_update_view(agent, server_version)},
        server_version=server_version,
        device=SimpleNamespace(id="device-test"),
        supports=SimpleNamespace(
            agent_update=True,
            agent_rollback=False,
            agent_rotate_token=False,
            agent_set_interval=True,
            diagnostics=False,
        ),
        section="management",
    )


def test_old_source_is_not_a_red_error_or_available_update_in_web():
    html = render_agent(
        {
            "version": "1.0.0",
            "available_version": "0.55.5",
            "last_update_status": "skipped",
            "last_update_error": "downgrade blocked",
        }
    )
    assert "downgrade blocked" not in html
    assert "Источник старее агента" in html
    assert "Доступное обновление</dt><dd>Нет" in html


def test_newer_agent_does_not_get_a_downgrade_update_banner():
    html = render_agent({"version": "1.0.0", "available_version": "0.55.5"}, "0.55.5")
    assert "Сервер старее агента" in html
    assert "Агент требует обновления" not in html


def test_outdated_agent_still_gets_an_update_banner():
    html = render_agent({"version": "0.55.5", "available_version": "1.0.0"})
    assert "Агент требует обновления" in html
    assert "Доступное обновление</dt><dd>1.0.0" in html
