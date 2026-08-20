from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


USERNAME = "deployment@example.test"
PASSWORD = "deployment-acceptance-password"


def request(server: str, path: str, *, body: dict | None = None, token: str = ""):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(server.rstrip("/") + path, data=payload, headers=headers)
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw) if raw else None


def setup(server: str) -> None:
    status, _ = request(
        server,
        "/api/v1/setup/complete",
        body={
            "username": USERNAME,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "server_url": server,
        },
    )
    if status != 200:
        raise SystemExit(f"clean setup failed with HTTP {status}")


def login(server: str) -> str:
    status, result = request(
        server,
        "/api/v1/auth/login",
        body={"username": USERNAME, "password": PASSWORD},
    )
    if status != 200:
        raise SystemExit(f"login failed with HTTP {status}")
    return str(result["access_token"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify", "clean-install"))
    parser.add_argument("--server", required=True)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()

    if args.mode == "clean-install":
        setup(args.server)
        token = login(args.server)
        status, devices = request(args.server, "/api/v1/devices", token=token)
        if status != 200 or devices != []:
            raise SystemExit("clean install did not start with an empty device list")
        print("clean install accepted")
        return

    if args.state is None:
        raise SystemExit("--state is required")

    if args.mode == "seed":
        setup(args.server)
        token = login(args.server)
        status, provisioned = request(
            args.server,
            "/api/v1/devices/provision",
            token=token,
            body={
                "name": "Persistent router",
                "hostname": "upgrade-router",
                "model": "CI",
                "firmware": "OpenWrt",
            },
        )
        if status != 200:
            raise SystemExit(f"device provision failed with HTTP {status}")
        args.state.write_text(
            json.dumps({"device_id": provisioned["device_id"]}), encoding="utf-8"
        )
        print("persistent state created")
        return

    expected = json.loads(args.state.read_text(encoding="utf-8"))
    token = login(args.server)
    status, devices = request(args.server, "/api/v1/devices", token=token)
    if status != 200:
        raise SystemExit(f"device list failed with HTTP {status}")
    if expected["device_id"] not in {item["id"] for item in devices}:
        raise SystemExit("persistent device disappeared after image update")
    print("persistent update accepted")


if __name__ == "__main__":
    main()
