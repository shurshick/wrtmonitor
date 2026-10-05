import json
import subprocess
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "lib" / "diagnostics.sh"


@pytest.mark.parametrize(
    "exit_code,http,expected",
    [
        (6, "000", "dns_failed"),
        (7, "000", "server_unreachable"),
        (28, "000", "connection_timeout"),
        (60, "000", "tls_failed"),
        (0, "503", "backend_unavailable"),
        (0, "401", "authorization_failed"),
        (0, "000", "transport_failed"),
    ],
)
def test_connection_failures_have_code_and_action(exit_code, http, expected):
    script = f"""
    . '{LIB.as_posix()}'
    server_url() {{ printf 'https://example.test'; }}
    curl() {{ printf '{http}'; return {exit_code}; }}
    check_server_json
    """
    result = subprocess.run(
        ["sh", "-c", script], check=True, capture_output=True, text=True
    )
    diagnostic = json.loads(result.stdout)
    assert diagnostic["code"] == expected
    assert diagnostic["status"] == "failed"
    assert diagnostic["action"]
    assert "example.test" not in result.stdout
