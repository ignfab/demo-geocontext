"""Tests for app.services.db.is_database_healthy."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

import app.services.db as db_service


def test_is_database_healthy_returns_true_and_closes_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeDatabase:
        async def is_healthy(self) -> bool:
            calls.append("is_healthy")
            return True

    @asynccontextmanager
    async def fake_get_database():
        calls.append("enter")
        try:
            yield FakeDatabase()
        finally:
            calls.append("exit")

    monkeypatch.setattr(db_service, "get_database", fake_get_database)

    healthy = asyncio.run(db_service.is_database_healthy())

    assert healthy is True
    assert calls == ["enter", "is_healthy", "exit"]


def test_is_database_healthy_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        async def is_healthy(self) -> bool:
            return False

    @asynccontextmanager
    async def fake_get_database():
        yield FakeDatabase()

    monkeypatch.setattr(db_service, "get_database", fake_get_database)

    healthy = asyncio.run(db_service.is_database_healthy())

    assert healthy is False


def test_is_database_healthy_propagates_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def fake_get_database():
        raise RuntimeError("Invalid DB_URI")
        yield

    monkeypatch.setattr(db_service, "get_database", fake_get_database)

    with pytest.raises(RuntimeError, match="Invalid DB_URI"):
        asyncio.run(db_service.is_database_healthy())
