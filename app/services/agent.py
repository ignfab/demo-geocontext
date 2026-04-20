import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

from ..config import get_mcp_servers_config

from langchain.chat_models import init_chat_model
from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent

from ..config import MODEL_NAME, TEMPERATURE, check_api_key
from ..tools import create_map
from .db import get_database

logger = logging.getLogger(__name__)


def format_tool_error(exc: Exception) -> str:
    """Format a recoverable tool error for the model."""

    # Only MCP tool-result errors should be recoverable by the model. Protocol,
    # transport, or session errors must still bubble up as hard failures.
    if not isinstance(exc, ToolException):
        raise exc

    logger.warning("Tool failed: %s", exc, exc_info=True)
    return (
        f"Erreur lors de l'appel de l'outil: {exc}\n\n"
        "Corrige les arguments de l'outil et réessaie si possible."
    )


@asynccontextmanager
async def get_agent() -> AsyncIterator[CompiledStateGraph]:
    """Ouvre la base (``database_lifecycle``) et compile le graphe avec son checkpointer (mémoire si pas de BDD)."""
    async with get_database() as db:
        # TODO : improve session management to avoid creation of a session
        # for each tool call
        logger.info("Loading tools from MCP servers...")
        mcp_client = MultiServerMCPClient(get_mcp_servers_config())
        tools = await mcp_client.get_tools()
        logger.info("Loaded %s tools", len(tools))

        logger.info("Add demo specific tools...")
        tools.append(create_map)

        check_api_key()
        logger.info("Create chat model: %s (temperature=%s)", MODEL_NAME, TEMPERATURE)
        model = init_chat_model(MODEL_NAME, temperature=TEMPERATURE)

        logger.info("Create agent (checkpointer: %s)", type(db.checkpointer))
        agent = create_agent(
            model=model,
            tools=tools,
            checkpointer=db.checkpointer,
            middleware=[
                ToolRetryMiddleware(
                    max_retries=0,
                    retry_on=(ToolException,),
                    on_failure=format_tool_error,
                )
            ],
        )

        logger.info(f"Agent created successfully")
        yield agent


async def get_messages(graph: CompiledStateGraph, thread_id: str) -> AsyncIterator[Any]:
    """Itère sur l'historique des messages d'un thread."""
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)

    if "messages" in state.values:
        messages = state.values["messages"]
        for message in messages:
            yield message
