from __future__ import annotations

import json
import re
from functools import lru_cache
from time import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _board_identity(payload: dict[str, Any]) -> tuple[str, str, str]:
    board = payload.get("board") or {}
    release = board.get("release") or {}
    return (
        str(release.get("version") or "").strip(),
        str(release.get("target") or "").strip().strip("/"),
        str(board.get("board_name") or "").strip(),
    )


@lru_cache(maxsize=32)
def _profiles(version: str, target: str) -> dict[str, Any]:
    url = f"https://downloads.openwrt.org/releases/{version}/targets/{target}/profiles.json"
    request = Request(url, headers={"User-Agent": "WrtMonitor firmware catalog"})
    with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed HTTPS host
        return json.loads(response.read(8 * 1024 * 1024))


@lru_cache(maxsize=2)
def _overview_for_hour(_hour: int) -> dict[str, Any]:
    request = Request(
        "https://sysupgrade.openwrt.org/json/v1/overview.json",
        headers={"User-Agent": "WrtMonitor firmware catalog"},
    )
    with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed HTTPS host
        return json.loads(response.read(8 * 1024 * 1024))


def _overview() -> dict[str, Any]:
    return _overview_for_hour(int(time() // 3600))


def _version_key(value: str) -> tuple[tuple[int, ...], int, int]:
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-rc(\d+))?", value)
    if not match:
        return ((), -2, 0)
    numbers = tuple(int(part) for part in match.group(1).split("."))
    release_candidate = match.group(2)
    return (
        numbers,
        0 if release_candidate is None else -1,
        int(release_candidate or 0),
    )


def _available_version(
    installed_version: str, target: str, overview: dict[str, Any]
) -> str:
    branch_name = ".".join(installed_version.split(".")[:2])
    branch = (overview.get("branches") or {}).get(branch_name) or {}
    if not branch.get("enabled", False) or target not in (branch.get("targets") or {}):
        return ""
    installed_key = _version_key(installed_version)
    candidates = [
        str(candidate)
        for candidate in branch.get("versions") or []
        if _version_key(str(candidate)) > installed_key
    ]
    return max(candidates, key=_version_key, default="")


def _resolve_profile(
    profiles: dict[str, Any], board_name: str
) -> dict[str, Any] | None:
    profile_map = profiles.get("profiles") or {}
    direct = profile_map.get(board_name)
    if isinstance(direct, dict):
        return direct
    normalized = re.sub(r"[^a-z0-9]+", "_", board_name.lower()).strip("_")
    alias = profile_map.get(normalized)
    if isinstance(alias, dict):
        return alias
    for profile in profile_map.values():
        if isinstance(profile, dict) and board_name in (
            profile.get("supported_devices") or []
        ):
            return profile
    return None


def _profile_title(profile: dict[str, Any], board_name: str) -> str:
    titles = profile.get("titles") or []
    if not titles or not isinstance(titles[0], dict):
        return board_name
    vendor = str(titles[0].get("vendor") or "").strip()
    model = str(titles[0].get("model") or "").strip()
    return " ".join(part for part in (vendor, model) if part) or board_name


def firmware_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    version, target, board_name = _board_identity(payload)
    result: dict[str, Any] = {
        "source": "openwrt-asu-overview+profiles-json",
        "version": version,
        "installed_version": version,
        "available_version": "",
        "target": target,
        "board_name": board_name,
        "images": [],
        "status": "unsupported",
        "error": None,
    }
    if not version or not target or not board_name:
        result["error"] = "Router did not report OpenWrt release target and board name"
        return result
    try:
        available_version = _available_version(version, target, _overview())
        if not available_version:
            result["status"] = "observed"
            result["error"] = (
                "The latest OpenWrt release for this branch is already installed"
            )
            return result
        result["available_version"] = available_version
        profiles = _profiles(available_version, target)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        result["status"] = "error"
        result["error"] = f"OpenWrt catalog is unavailable: {exc}"
        return result
    profile = _resolve_profile(profiles, board_name)
    if not isinstance(profile, dict):
        result["error"] = (
            f"Board {board_name} is absent from the official OpenWrt catalog"
        )
        return result
    base_url = (
        f"https://downloads.openwrt.org/releases/{result['available_version']}"
        f"/targets/{target}/"
    )
    result["images"] = [
        {
            "name": str(image.get("name") or ""),
            "label": (
                f"OpenWrt {result['available_version']} · "
                f"{_profile_title(profile, board_name)}"
            ),
            "url": base_url + str(image.get("name") or ""),
            "sha256": str(image.get("sha256") or ""),
            "type": str(image.get("type") or ""),
            "model": board_name,
        }
        for image in profile.get("images") or []
        if isinstance(image, dict)
        and image.get("name")
        and image.get("sha256")
        and "sysupgrade" in str(image.get("type") or image.get("name") or "")
    ]
    result["status"] = "observed" if result["images"] else "unsupported"
    if not result["images"]:
        result["error"] = "The official profile does not contain a sysupgrade image"
    return result


__all__ = ["firmware_catalog"]
