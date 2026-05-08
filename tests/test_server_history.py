"""Tests for app.server.load_conversation_history."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import app.server as server


def test_load_conversation_history_returns_empty_when_graph_or_thread_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "graph", None)

    assert asyncio.run(server.load_conversation_history("thread-1")) == []

    monkeypatch.setattr(server, "graph", object())
    assert asyncio.run(server.load_conversation_history("")) == []


def test_load_conversation_history_accepts_tuple_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "graph", object())

    human = SimpleNamespace(type="human", content="bonjour")
    ai = SimpleNamespace(type="ai", content="salut")

    async def fake_get_messages(_graph, _thread_id):
        yield (human, "2026-01-01T00:00:00Z")
        yield (ai, "2026-01-01T00:00:01Z")

    def fake_to_gradio_message(message):
        assert not isinstance(message, tuple)
        return {"role": message.type, "content": message.content}

    monkeypatch.setattr(server, "get_messages", fake_get_messages)
    monkeypatch.setattr(server, "to_gradio_message", fake_to_gradio_message)

    history = asyncio.run(server.load_conversation_history("thread-1"))

    assert history == [
        {"role": "human", "content": "bonjour"},
        {"role": "ai", "content": "salut"},
    ]

