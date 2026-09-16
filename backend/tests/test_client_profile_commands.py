from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.api import clients as api
from backend.app.schemas import ClientProfileRequest
from backend.app.services import client_profile_commands as service
from backend.app.web import routes_clients as web


@pytest.fixture
def context(monkeypatch):
    profile = SimpleNamespace(
        id=uuid4(), device_id=uuid4(), name="Guests", policy={"blocked": True}
    )
    clients = [
        SimpleNamespace(mac="02:00:00:00:00:01", profile_id=profile.id, policy={}),
        SimpleNamespace(
            mac="02:00:00:00:00:02",
            profile_id=profile.id,
            policy={
                "blocked": False,
                "qos": {"download_kbps": 5000, "upload_kbps": 1000},
            },
        ),
    ]
    db = MagicMock()
    db.get.return_value = profile
    db.scalars.return_value.all.return_value = clients
    db.scalars.return_value.first.return_value = None
    queue = MagicMock(side_effect=lambda *a, **k: SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(service, "create_device_command", queue)
    monkeypatch.setattr(service, "assigned_wifi_interfaces", lambda *a: ["guest"])
    monkeypatch.setattr(service, "device_supports", lambda *a: True)
    return SimpleNamespace(
        profile=profile,
        clients=clients,
        db=db,
        queue=queue,
        user=SimpleNamespace(id=uuid4()),
    )


def test_update_reapplies_to_network_and_clients_preserving_overrides(context):
    c = context
    ids = service.queue_profile_commands(
        c.db, c.profile, created_by=c.user.id, source="web"
    )
    calls = [item.kwargs for item in c.queue.call_args_list]
    assert len(ids) == 3
    assert [item["command_type"] for item in calls] == [
        "wifi.set_access_profile",
        "client.set_policy",
        "client.set_policy",
    ]
    assert calls[1]["payload"]["blocked"] is True
    assert calls[2]["payload"]["blocked"] is False
    assert calls[2]["payload"]["qos"]["download_kbps"] == 5000
    assert all(item["device_id"] == c.profile.device_id for item in calls)
    query = c.db.scalars.call_args.args[0].compile().params
    assert c.profile.device_id in query.values() and c.profile.id in query.values()
    c.db.commit.assert_not_called()


def test_delete_clears_inheritance_but_retains_individual_policy(context):
    c = context
    service.queue_profile_commands(
        c.db, c.profile, created_by=c.user.id, source="api", removing=True
    )
    calls = [item.kwargs for item in c.queue.call_args_list]
    assert calls[0]["payload"]["enabled"] is False
    assert calls[1]["payload"]["blocked"] is False
    assert calls[1]["payload"]["qos"]["download_kbps"] == 0
    assert calls[2]["payload"]["qos"]["download_kbps"] == 5000
    assert all(client.profile_id is None for client in c.clients)


def test_missing_shaping_capability_queues_nothing(context, monkeypatch):
    c = context
    monkeypatch.setattr(service, "device_supports", lambda *a: False)
    with pytest.raises(HTTPException, match="clients.shaping"):
        service.queue_profile_commands(
            c.db, c.profile, created_by=c.user.id, source="api"
        )
    c.queue.assert_not_called()


def test_validation_failure_does_not_detach_clients_or_queue_partial_update(
    context, monkeypatch
):
    c = context

    def validate(**kwargs):
        if kwargs["command_type"] == "client.set_policy":
            raise HTTPException(409, "unsupported client policy")
        return kwargs["payload"]

    monkeypatch.setattr(service, "validate_command_request", validate)
    with pytest.raises(HTTPException):
        service.queue_profile_commands(
            c.db, c.profile, created_by=c.user.id, source="api", removing=True
        )
    c.queue.assert_not_called()
    assert all(client.profile_id == c.profile.id for client in c.clients)


@pytest.mark.parametrize("surface", ["api", "web"])
@pytest.mark.parametrize("removing", [False, True])
def test_both_transports_apply_profile_to_clients(
    context, monkeypatch, surface, removing
):
    c = context
    module = api if surface == "api" else web
    monkeypatch.setattr(module, "get_user_device_or_404", lambda *a: None)
    monkeypatch.setattr(module, "audit", lambda *a: None)
    if surface == "api":
        monkeypatch.setattr(api, "get_profile", lambda *a: c.profile)
        kwargs = dict(
            device_id=c.profile.device_id, profile_id=c.profile.id, user=c.user, db=c.db
        )
        if removing:
            api.delete_profile(**kwargs)
        else:
            api.update_profile(
                **kwargs,
                payload=ClientProfileRequest(name="Guests", policy={"blocked": False}),
            )
    else:
        monkeypatch.setattr(web, "web_user_from_session", lambda *a: c.user)
        monkeypatch.setattr(web, "require_web_csrf", lambda *a: None)
        kwargs = dict(
            device_id=c.profile.device_id,
            profile_id=c.profile.id,
            db=c.db,
            config=object(),
            wrtmonitor_session="session",
            csrf_token="csrf",
        )
        if removing:
            web.web_delete_client_profile(**kwargs)
        else:
            web.web_update_client_profile(
                **kwargs,
                name="Guests",
                blocked=False,
                schedule_enabled=False,
                weekdays=[],
                start="",
                stop="",
                download_kbps=0,
                upload_kbps=0,
            )
    assert c.queue.call_count == 3
    assert all(call.kwargs["source"] == surface for call in c.queue.call_args_list)
    c.db.commit.assert_called_once()
