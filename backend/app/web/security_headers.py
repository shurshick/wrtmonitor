import re

from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if (
            re.fullmatch(r"/devices/[0-9a-fA-F-]{36}", request.url.path)
            and request.query_params.get("section") == "terminal"
            and response.headers.get("content-type", "").startswith("text/html")
        ):
            # xterm's DOM renderer generates style elements for cell geometry and ANSI.
            # Scripts and style attributes retain the default self-only policy.
            response.headers["Content-Security-Policy"] += (
                "; style-src-elem 'self' 'unsafe-inline'"
            )
        return response
