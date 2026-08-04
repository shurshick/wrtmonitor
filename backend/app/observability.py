from __future__ import annotations

from collections import defaultdict
import json
import logging
import re
from threading import Lock
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("wrtmonitor.requests")
_lock = Lock()
_request_count: dict[tuple[str, str, int], int] = defaultdict(int)
_request_duration: dict[tuple[str, str], float] = defaultdict(float)
_request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_known_methods = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


def _route_name(request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", None) or "<unmatched>")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not _request_id_pattern.fullmatch(request_id):
            request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = perf_counter() - started
            route = _route_name(request)
            with _lock:
                method = request.method if request.method in _known_methods else "OTHER"
                _request_count[(method, route, status)] += 1
                _request_duration[(method, route)] += duration
            if "response" in locals():
                response.headers["X-Request-ID"] = request_id
                response.headers["Server-Timing"] = f"app;dur={duration * 1000:.1f}"
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration * 1000, 2),
                    },
                    separators=(",", ":"),
                )
            )


def prometheus_metrics() -> str:
    from .services.realtime import broker

    lines = [
        "# HELP wrtmonitor_http_requests_total HTTP requests processed.",
        "# TYPE wrtmonitor_http_requests_total counter",
    ]
    with _lock:
        counts = list(_request_count.items())
        durations = list(_request_duration.items())
    for (method, route, status), value in sorted(counts):
        labels = f'method="{method}",route="{route}",status="{status}"'
        lines.append(f"wrtmonitor_http_requests_total{{{labels}}} {value}")
    lines.extend(
        [
            "# HELP wrtmonitor_http_request_duration_seconds_sum Total HTTP request time.",
            "# TYPE wrtmonitor_http_request_duration_seconds_sum counter",
        ]
    )
    for (method, route), value in sorted(durations):
        labels = f'method="{method}",route="{route}"'
        lines.append(
            f"wrtmonitor_http_request_duration_seconds_sum{{{labels}}} {value:.6f}"
        )
    for name, value in broker.metrics().items():
        lines.append(f"wrtmonitor_realtime_{name} {value}")
    return "\n".join(lines) + "\n"
