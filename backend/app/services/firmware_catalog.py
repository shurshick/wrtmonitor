from __future__ import annotations

import json
from functools import lru_cache
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


def firmware_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    version, target, board_name = _board_identity(payload)
    result: dict[str, Any] = {
        "source": "openwrt-profiles-json",
        "version": version,
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
        profiles = _profiles(version, target)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        result["status"] = "error"
        result["error"] = f"OpenWrt catalog is unavailable: {exc}"
        return result
    profile = (profiles.get("profiles") or {}).get(board_name)
    if not isinstance(profile, dict):
        result["error"] = (
            f"Board {board_name} is absent from the official OpenWrt catalog"
        )
        return result
    base_url = f"https://downloads.openwrt.org/releases/{version}/targets/{target}/"
    result["images"] = [
        {
            "name": str(image.get("name") or ""),
            "label": str(image.get("name") or "sysupgrade image"),
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
