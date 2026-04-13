"""Tests for app.services.auth.get_current_user."""

from __future__ import annotations

from starlette.requests import Request

from app.models import User
from app.services.auth import get_current_user


def _make_request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "query_string": b"",
        "headers": raw,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, str]:
        return {"type": "http.disconnect"}

    return Request(scope, receive)


def test_get_current_user_defaults_when_no_forwarded_headers() -> None:
    request = _make_request({})
    user = get_current_user(request)
    assert user == User(
        id="anonymous",
        username="anonymous",
        email="anonymous@gpf.fr",
        groups=[],
    )


def test_get_current_user_from_forwarded_headers() -> None:
    request = _make_request(
        {
            "X-Forwarded-User": "sub-123",
            "X-Forwarded-Preferred-Username": "jdoe",
            "X-Forwarded-Email": "jdoe@example.org",
            "X-Forwarded-Groups": "editors, viewers",
        }
    )
    user = get_current_user(request)
    assert user == User(
        id="sub-123",
        username="jdoe",
        email="jdoe@example.org",
        groups=["editors", "viewers"],
    )


def test_get_current_user_groups_missing_header_is_empty_list() -> None:
    request = _make_request({"X-Forwarded-User": "u1"})
    user = get_current_user(request)
    assert user.groups == []


def test_get_current_user_groups_strips_and_skips_empty_segments() -> None:
    request = _make_request({"X-Forwarded-Groups": " a ,  , b "})
    user = get_current_user(request)
    assert user.groups == ["a", "b"]


def test_get_current_user_groups_empty_string_yields_no_groups() -> None:
    request = _make_request({"X-Forwarded-Groups": ""})
    user = get_current_user(request)
    assert user.groups == []
