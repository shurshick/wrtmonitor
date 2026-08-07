import urllib.request
import urllib.parse
import json

base_url = "https://sync.bghitech.ru/api/v1"

# Login
data = json.dumps({"username": "shurshick@bk.ru", "password": "D2e42204!@"}).encode()
req = urllib.request.Request(f"{base_url}/auth/login", data=data, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as response:
    token = json.loads(response.read())["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# Get devices
req = urllib.request.Request(f"{base_url}/devices", headers=headers)
with urllib.request.urlopen(req) as response:
    devices = json.loads(response.read())

import asyncio
import websockets

async def test_ws():
    uri = f"wss://sync.bghitech.ru/api/v1/devices/{devices[0]['id']}/ssh/ws"
    # We must pass the cookie
    try:
        async with websockets.connect(uri, additional_headers={"Cookie": f"wrtmonitor_session={token}"}) as ws:
            print("Connected to WS successfully!")
            await ws.send("test")
            response = await ws.recv()
            print(f"Received: {response}")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"WS HTTP error: {e.status_code}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WS Closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"WS error: {e}")

# asyncio.run(test_ws())

for dev in devices:
    print(f"Device: {dev.get('id')} - Name: {dev.get('name')} - Status: {dev.get('status')} - Last Seen: {dev.get('last_seen')}")
    # Get commands
    req = urllib.request.Request(f"{base_url}/devices/{dev['id']}/commands", headers=headers)
    with urllib.request.urlopen(req) as response:
        commands = json.loads(response.read())
        for c in commands[:10]:
            if c.get('capability') == 'agent.ssh_session':
                print(f"  Command: {c.get('capability')} - Status: {c.get('status')} - Result: {c.get('result')}")
