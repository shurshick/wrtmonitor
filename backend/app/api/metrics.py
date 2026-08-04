from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ..observability import ObservabilityMiddleware
from ..services.realtime import broker

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics() -> str:
    obs = ObservabilityMiddleware.metrics()
    rt = broker.metrics()
    
    lines = [
        "# HELP wrtmonitor_http_requests_total Total HTTP requests",
        "# TYPE wrtmonitor_http_requests_total counter",
        f"wrtmonitor_http_requests_total {obs['requests']}",
        "",
        "# HELP wrtmonitor_http_errors_total Total HTTP errors (5xx)",
        "# TYPE wrtmonitor_http_errors_total counter",
        f"wrtmonitor_http_errors_total {obs['errors']}",
        "",
        "# HELP wrtmonitor_realtime_long_poll_active Current active long-poll requests",
        "# TYPE wrtmonitor_realtime_long_poll_active gauge",
        f"wrtmonitor_realtime_long_poll_active {rt['long_poll_active']}",
        "",
        "# HELP wrtmonitor_realtime_long_poll_wakeups Total long-poll wakeups by broker",
        "# TYPE wrtmonitor_realtime_long_poll_wakeups counter",
        f"wrtmonitor_realtime_long_poll_wakeups {rt['long_poll_wakeups']}",
        "",
        "# HELP wrtmonitor_realtime_events_published Total real-time events published",
        "# TYPE wrtmonitor_realtime_events_published counter",
        f"wrtmonitor_realtime_events_published {rt['events_published']}",
        "",
        "# HELP wrtmonitor_realtime_sse_subscribers Current active SSE subscribers",
        "# TYPE wrtmonitor_realtime_sse_subscribers gauge",
        f"wrtmonitor_realtime_sse_subscribers {rt['sse_subscribers']}",
    ]
    return "\n".join(lines) + "\n"
