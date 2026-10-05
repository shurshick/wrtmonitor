import re
from typing import Any

from ..config import APP_VERSION

_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?(?:\+.*)?$")


def version_key(value: str) -> tuple[int, int, int, int, int] | None:
    match = _SEMVER.fullmatch(value.strip())
    if match is None:
        return None
    major, minor, patch, rc = match.groups()
    try:
        return int(major), int(minor), int(patch), int(rc is None), int(rc or 0)
    except ValueError:
        return None


def agent_update_view(agent: dict[str, Any], server_version: str = APP_VERSION) -> dict:
    installed = version_key(str(agent.get("version") or ""))
    source_version = str(agent.get("available_version") or "").strip()
    source = version_key(source_version)
    server = version_key(server_version)
    error = str(agent.get("last_update_error") or "").strip()
    legacy_downgrade = (
        error == "downgrade blocked"
        and agent.get("last_update_status") == "skipped"
        and installed is not None
        and source is not None
        and source < installed
    )
    state = "unknown"
    if agent.get("last_update_status") == "failed" or (error and not legacy_downgrade):
        state = "error"
    elif installed is not None and source is not None:
        state = (
            "available"
            if source > installed
            else "current"
            if source == installed
            else "source_older"
        )
    relation = "unknown"
    if installed is not None and server is not None:
        relation = (
            "agent_older"
            if installed < server
            else "agent_newer"
            if installed > server
            else "equal"
        )
    return {
        "state": state,
        "source_version": source_version or None,
        "available_version": source_version if state == "available" else None,
        "error": error if state == "error" else None,
        "server_relation": relation,
    }


def with_agent_update_view(agent: dict[str, Any]) -> dict[str, Any]:
    return {**agent, "update_view": agent_update_view(agent)}
