from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from ..config import get_mcp_servers_config

_client: MultiServerMCPClient | None = None


def get_mcp_client() -> MultiServerMCPClient:
    global _client
    if _client is None:
        _client = MultiServerMCPClient(get_mcp_servers_config())
    return _client


async def get_mcp_tools() -> list[Any]:
    """Get MCP tools from a shared client (static config)."""
    return list(await get_mcp_client().get_tools())
