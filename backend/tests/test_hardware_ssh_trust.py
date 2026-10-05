import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("explicit", [True, False])
def test_runner_uses_only_the_selected_trust_store(monkeypatch, explicit):
    source = Path(__file__).resolve().parents[2] / "scripts/hardware_certify.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    ssh_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Ssh"
    )
    client = MagicMock()
    policy = type("RejectPolicy", (), {})
    namespace = {
        "os": os,
        "paramiko": SimpleNamespace(SSHClient=lambda: client, RejectPolicy=policy),
    }
    isolated = ast.Module(
        body=[ast.parse("from __future__ import annotations").body[0], ssh_class],
        type_ignores=[],
    )
    exec(compile(isolated, str(source), "exec"), namespace)
    if explicit:
        monkeypatch.setenv("WRTMONITOR_SSH_KNOWN_HOSTS", "verified-known-hosts")
    else:
        monkeypatch.delenv("WRTMONITOR_SSH_KNOWN_HOSTS", raising=False)
    namespace["Ssh"](
        SimpleNamespace(host="router.invalid", ssh_user="root"), "test-only"
    )
    if explicit:
        client.load_host_keys.assert_called_once_with("verified-known-hosts")
        client.load_system_host_keys.assert_not_called()
    else:
        client.load_system_host_keys.assert_called_once_with()
        client.load_host_keys.assert_not_called()
    assert isinstance(client.set_missing_host_key_policy.call_args.args[0], policy)
