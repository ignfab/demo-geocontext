"""Tests for recoverable agent tool errors."""

from __future__ import annotations

import asyncio

from langchain.agents.middleware import ToolCallRequest, ToolRetryMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from app.services.agent import format_tool_error


def _request() -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={
            "name": "gpf_wfs_get_features",
            "args": {"typename": "BDTOPO_V3:surface_hydrographique"},
            "id": "call-1",
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=None,
    )


def test_tool_error_middleware_returns_error_tool_message() -> None:
    # MCP CallToolResult(isError=True) is converted by langchain-mcp-adapters
    # into ToolException. This is the only error family we want to expose to the
    # model as a recoverable ToolMessage.
    middleware = ToolRetryMiddleware(
        max_retries=0,
        retry_on=(ToolException,),
        on_failure=format_tool_error,
    )

    def handler(_request: ToolCallRequest) -> ToolMessage:
        raise ToolException("La propriété 'nom_c_eau' n'existe pas")

    result = middleware.wrap_tool_call(_request(), handler)

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.name == "gpf_wfs_get_features"
    assert result.tool_call_id == "call-1"
    assert "nom_c_eau" in result.content
    assert "Corrige les arguments" in result.content


def test_tool_error_middleware_returns_async_error_tool_message() -> None:
    # The Gradio/LangGraph path is async, so keep coverage on awrap_tool_call,
    # not only the sync wrapper.
    middleware = ToolRetryMiddleware(
        max_retries=0,
        retry_on=(ToolException,),
        on_failure=format_tool_error,
    )

    async def handler(_request: ToolCallRequest) -> ToolMessage:
        raise ToolException("propriété inconnue")

    result = asyncio.run(middleware.awrap_tool_call(_request(), handler))

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.tool_call_id == "call-1"
    assert "propriété inconnue" in result.content


def test_tool_error_middleware_does_not_swallow_non_tool_exceptions() -> None:
    # Transport/session/runtime failures are not normal tool results. They must
    # bubble up so operators see the real failure instead of a model-readable
    # tool error.
    middleware = ToolRetryMiddleware(
        max_retries=0,
        retry_on=(ToolException,),
        on_failure=format_tool_error,
    )

    def handler(_request: ToolCallRequest) -> ToolMessage:
        raise RuntimeError("JSON-RPC connection closed")

    try:
        middleware.wrap_tool_call(_request(), handler)
    except RuntimeError as exc:
        assert "JSON-RPC connection closed" in str(exc)
    else:
        raise AssertionError("RuntimeError should not be converted to a ToolMessage")


def test_tool_error_middleware_does_not_swallow_json_rpc_errors() -> None:
    # JSON-RPC protocol errors are raised by the MCP SDK as McpError. Even when
    # the message looks tool-related, it is not a CallToolResult(isError=True),
    # so it should remain a hard protocol failure.
    middleware = ToolRetryMiddleware(
        max_retries=0,
        retry_on=(ToolException,),
        on_failure=format_tool_error,
    )
    json_rpc_error = McpError(
        ErrorData(code=-32602, message="Unknown tool: invalid_tool_name")
    )

    def handler(_request: ToolCallRequest) -> ToolMessage:
        raise json_rpc_error

    try:
        middleware.wrap_tool_call(_request(), handler)
    except McpError as exc:
        assert exc.error.code == -32602
        assert exc.error.message == "Unknown tool: invalid_tool_name"
    else:
        raise AssertionError("McpError should not be converted to a ToolMessage")
