"""Tests for app.services.mcp_client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import mcp_client


@pytest.fixture(autouse=True)
def reset_mcp_client_singleton() -> None:
    mcp_client._client = None
    yield
    mcp_client._client = None


def test_get_mcp_client_creates_singleton_once() -> None:
    fake = MagicMock()
    cfg = {"geocontext": {"command": "npx", "args": ["-y", "@ignfab/geocontext"]}}
    with (
        patch.object(mcp_client, "get_mcp_servers_config", return_value=cfg),
        patch.object(mcp_client, "MultiServerMCPClient", return_value=fake) as ctor,
    ):
        first = mcp_client.get_mcp_client()
        second = mcp_client.get_mcp_client()
    assert first is second is fake
    ctor.assert_called_once_with(cfg)


def test_get_mcp_tools_returns_list_from_client_get_tools() -> None:
    tools = [MagicMock(name="tool_a"), MagicMock(name="tool_b")]
    fake_client = MagicMock()
    fake_client.get_tools = AsyncMock(return_value=tools)

    async def _run() -> list[object]:
        with (
            patch.object(mcp_client, "get_mcp_servers_config", return_value={}),
            patch.object(mcp_client, "MultiServerMCPClient", return_value=fake_client),
        ):
            return await mcp_client.get_mcp_tools()

    out = asyncio.run(_run())
    assert out == tools
    fake_client.get_tools.assert_awaited_once()
