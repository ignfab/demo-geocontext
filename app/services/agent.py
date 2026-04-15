import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from ..config import get_mcp_servers_config

from langchain.chat_models import init_chat_model
from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent

from ..config import MODEL_NAME, TEMPERATURE, check_api_key
from ..tools import create_map
from .db import get_database

logger = logging.getLogger(__name__)

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
            #system_prompt=SYSTEM_PROMPT,
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
