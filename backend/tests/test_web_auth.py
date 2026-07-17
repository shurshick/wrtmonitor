from uuid import uuid4

from starlette.requests import Request

import backend.app.web.routes as routes
from backend.app.config import Settings
from backend.app.models import User


def make_request(*, scheme: str = "http", forwarded_proto: str | None = None):
    headers = []
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": scheme,
            "server": ("testserver", 443 if scheme == "https" else 80),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
            "path": "/login",
            "query_string": b"",
            "headers": headers,
        }
    )


def config(*, allow_insecure_local: bool = False) -> Settings:
    return Settings(
        public_server_url="https://monitor.example.ru",
        database_url="postgresql+psycopg://user:password@postgres:5432/wrtmonitor",
        bind_host="0.0.0.0",
        bind_port=8080,
        jwt_secret="test-secret-value-with-more-than-32-characters",
        default_locale="ru",
        allow_insecure_local=allow_insecure_local,
        allow_insecure_dev_defaults=False,
        enable_api_docs=False,
    )


def test_reverse_proxy_https_header_is_respected():
    assert routes.request_uses_https(make_request(forwarded_proto="https"))
    assert not routes.request_uses_https(make_request(scheme="http"))


def test_web_login_rejects_plain_http_when_secure_cookie_is_required(monkeypatch):
    monkeypatch.setattr(routes, "is_setup_required", lambda db, current: False)

    response = routes.login_form(
        make_request(scheme="http"),
        username="admin@example.com",
        password="correct-password",
        config=config(),
        db=object(),
    )

    assert response.status_code == 400
    assert "HTTP" in response.body.decode()
    assert "https://monitor.example.ru/login" in response.body.decode()


def test_web_login_sets_secure_cookie_and_checks_it_after_redirect(monkeypatch):
    user = User(
        id=uuid4(),
        username="admin@example.com",
        password_hash="hash",
        role="owner",
        disabled=False,
    )

    class Scalars:
        def first(self):
            return user

    class Db:
        def scalars(self, statement):
            return Scalars()

        def commit(self):
            return None

    monkeypatch.setattr(routes, "is_setup_required", lambda db, current: False)
    monkeypatch.setattr(routes, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(routes, "audit", lambda *args, **kwargs: None)

    response = routes.login_form(
        make_request(forwarded_proto="https"),
        username=" admin@example.com ",
        password="correct-password",
        config=config(),
        db=Db(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/devices?login=1"
    cookie = response.headers["set-cookie"]
    assert "wrtmonitor_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
