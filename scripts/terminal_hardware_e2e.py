"""Browser -> WrtMonitor -> OpenWrt PTY terminal hardware check."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.sync_api import sync_playwright


def terminal_text(page) -> str:
    return page.locator("[data-terminal-device]").evaluate(
        """root => {
          const terminal = root.wrtmonitorTerminal;
          if (!terminal) return '';
          const buffer = terminal.buffer.active;
          let text = '';
          for (let index = 0; index < buffer.length; index += 1) {
            text += (buffer.getLine(index)?.translateToString(true) || '') + '\\n';
          }
          return text;
        }"""
    )


def wait_for_terminal_text(page, expected: str, timeout: int = 45_000) -> None:
    page.wait_for_function(
        """expected => {
          const root = document.querySelector('[data-terminal-device]');
          const terminal = root?.wrtmonitorTerminal;
          if (!terminal) return false;
          const buffer = terminal.buffer.active;
          let text = '';
          for (let index = 0; index < buffer.length; index += 1) {
            text += buffer.getLine(index)?.translateToString(true) || '';
          }
          return text.includes(expected);
        }""",
        arg=expected,
        timeout=timeout,
    )


def wait_for_terminal_size(page, marker: str, timeout: int = 45_000) -> None:
    page.wait_for_function(
        """marker => {
          const root = document.querySelector('[data-terminal-device]');
          const terminal = root?.wrtmonitorTerminal;
          if (!terminal) return false;
          const buffer = terminal.buffer.active;
          let text = '';
          for (let index = 0; index < buffer.length; index += 1) {
            text += buffer.getLine(index)?.translateToString(true) || '';
          }
          return new RegExp(`${marker}:[0-9]+[ ]+[0-9]+`).test(text);
        }""",
        arg=marker,
        timeout=timeout,
    )


def resolve_device(server: str, username: str, password: str, selector: str) -> str:
    with httpx.Client(base_url=server, timeout=20, follow_redirects=True) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        devices = client.get(
            "/api/v1/devices", headers={"Authorization": f"Bearer {token}"}
        )
        devices.raise_for_status()
    matches = [
        item
        for item in devices.json()
        if selector in {str(item.get("id")), str(item.get("name"))}
    ]
    if len(matches) != 1:
        names = ", ".join(str(item.get("name")) for item in devices.json())
        raise RuntimeError(
            f"router {selector!r} is ambiguous or missing; available: {names}"
        )
    return str(matches[0]["id"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a real OpenWrt PTY through the browser and WrtMonitor server"
    )
    parser.add_argument("--server", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--device", required=True, help="device UUID or exact name")
    parser.add_argument("--password-env", default="WRTMONITOR_E2E_PASSWORD")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--output", default="artifacts/terminal-hardware-e2e")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = os.getenv(args.password_env)
    if not password:
        raise RuntimeError(
            f"set {args.password_env} instead of putting a password in argv"
        )
    server = args.server.rstrip("/")
    parsed = urlparse(server)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("--server must be an absolute HTTP(S) URL")

    device_id = resolve_device(server, args.username, password, args.device)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    marker = f"WRTMONITOR_PTY_E2E_{secrets.token_hex(8)}"
    reconnect_marker = f"WRTMONITOR_PTY_RECONNECT_{secrets.token_hex(8)}"
    resize_marker = f"WRTMONITOR_PTY_RESIZE_{secrets.token_hex(8)}"
    started = time.monotonic()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{server}/login", wait_until="domcontentloaded")
        page.locator('input[name="username"]').fill(args.username)
        page.locator('input[name="password"]').fill(password)
        page.locator('button[type="submit"]').click()
        page.wait_for_url("**/devices")
        page.goto(
            f"{server}/devices/{device_id}?section=terminal",
            wait_until="domcontentloaded",
        )
        page.locator("#btn-terminal-connect").click()
        terminal_input = page.locator(".xterm-helper-textarea")
        terminal_input.wait_for(state="attached", timeout=15_000)
        page.locator('[data-terminal-state="connected"]').wait_for(timeout=45_000)
        terminal_input.evaluate("node => node.focus()")
        page.keyboard.type(f"printf '{marker}:%s\\n' \"$(uname -s)\"")
        page.keyboard.press("Enter")
        wait_for_terminal_text(page, f"{marker}:Linux")
        first_session_id = page.locator("[data-terminal-device]").get_attribute(
            "data-terminal-session"
        )
        if not first_session_id:
            raise RuntimeError("browser did not receive a terminal session identifier")

        page.set_viewport_size({"width": 1180, "height": 720})
        page.wait_for_timeout(750)
        rows, columns = page.locator("[data-terminal-device]").evaluate(
            "root => [root.wrtmonitorTerminal.rows, root.wrtmonitorTerminal.cols]"
        )
        terminal_input.evaluate("node => node.focus()")
        page.locator("[data-terminal-device]").evaluate(
            "(root, command) => root.wrtmonitorTerminal.paste(command)",
            f"printf '{resize_marker}:%s\\n' \"$(stty size)\"",
        )
        page.keyboard.press("Enter")
        try:
            wait_for_terminal_size(page, resize_marker)
        except Exception:
            (output / "terminal-resize-failure.txt").write_text(
                terminal_text(page), encoding="utf-8"
            )
            page.screenshot(
                path=str(output / "terminal-resize-failure.png"), full_page=True
            )
            raise
        first_captured = terminal_text(page)
        resize_match = re.search(
            rf"{re.escape(resize_marker)}:(\d+)\s+(\d+)", first_captured
        )
        actual_rows = int(resize_match.group(1)) if resize_match else None
        actual_columns = int(resize_match.group(2)) if resize_match else None

        page.locator("#btn-terminal-disconnect").click()
        page.locator('[data-terminal-state="closed"]').wait_for(timeout=15_000)
        page.locator("#btn-terminal-connect").click()
        page.locator('[data-terminal-state="connected"]').wait_for(timeout=45_000)
        second_session_id = page.locator("[data-terminal-device]").get_attribute(
            "data-terminal-session"
        )
        if not second_session_id or second_session_id == first_session_id:
            raise RuntimeError(
                "terminal reconnect reused the previous session identifier"
            )
        terminal_input.evaluate("node => node.focus()")
        page.keyboard.type(f"printf '{reconnect_marker}:%s\\n' \"$(uname -s)\"")
        page.keyboard.press("Enter")
        wait_for_terminal_text(page, f"{reconnect_marker}:Linux")

        captured = terminal_text(page)
        page.screenshot(path=str(output / "terminal.png"), full_page=True)
        page.keyboard.type("exit")
        page.keyboard.press("Enter")
        page.locator('[data-terminal-state="closed"]').wait_for(timeout=15_000)
        browser.close()

    (output / "terminal.txt").write_text(
        f"FIRST SESSION\n{first_captured}\n\nSECOND SESSION\n{captured}\n",
        encoding="utf-8",
    )

    report = {
        "tested_at": datetime.now(UTC).isoformat(),
        "server": server,
        "device_id": device_id,
        "session_id": second_session_id,
        "previous_session_id": first_session_id,
        "marker": marker,
        "status": "passed"
        if (actual_rows, actual_columns) == (rows, columns)
        else "failed",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "path": ["Chromium", "WebSocket", "WrtMonitor", "OpenWrt agent", "PTY"],
        "input_confirmed": f"{marker}:Linux" in first_captured,
        "resize_confirmed": (actual_rows, actual_columns) == (rows, columns),
        "expected_size": {"rows": rows, "columns": columns},
        "actual_size": {"rows": actual_rows, "columns": actual_columns},
        "reconnect_confirmed": f"{reconnect_marker}:Linux" in captured,
        "close_confirmed": True,
        "output_confirmed": f"{reconnect_marker}:Linux" in captured,
    }
    (output / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
