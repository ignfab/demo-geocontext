"""Tests for the dynamic tool selection middleware wiring."""

from __future__ import annotations

from langchain.agents.middleware import (
    LLMToolSelectorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from app.services import agent as agent_module


def test_build_middleware_enables_tool_selector(monkeypatch) -> None:
    # When dynamic tool selection is enabled, the selector must run first
    # (outermost) so the retry middleware only sees the reduced tool set.
    fake_model = GenericFakeChatModel(messages=iter([]))
    monkeypatch.setattr(agent_module, "is_tool_selection_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "check_api_key", lambda **_: None)
    monkeypatch.setattr(agent_module, "init_chat_model", lambda *a, **k: fake_model)
    monkeypatch.setattr(agent_module, "TOOL_SELECTOR_MAX_TOOLS", 5)
    monkeypatch.setattr(
        agent_module, "TOOL_SELECTOR_ALWAYS_INCLUDE", ["create_map", "geocode"]
    )

    middleware = agent_module.build_middleware()

    assert len(middleware) == 2
    selector, retry = middleware
    assert isinstance(selector, LLMToolSelectorMiddleware)
    assert isinstance(retry, ToolRetryMiddleware)
    assert selector.max_tools == 5
    assert selector.always_include == ["create_map", "geocode"]


def test_build_middleware_without_tool_selector(monkeypatch) -> None:
    # When disabled, only the retry middleware is present and behavior matches the
    # previous (all-tools) setup.
    monkeypatch.setattr(agent_module, "is_tool_selection_enabled", lambda: False)

    middleware = agent_module.build_middleware()

    assert len(middleware) == 1
    assert isinstance(middleware[0], ToolRetryMiddleware)
