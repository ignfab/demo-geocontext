import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langchain.agents.middleware import (
    AgentMiddleware,
    LLMToolSelectorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

from ..config import get_mcp_servers_config

from langchain.chat_models import init_chat_model
from langgraph.graph.state import CompiledStateGraph
from langchain.agents import create_agent

from ..config import (
    MODEL_NAME,
    TEMPERATURE,
    TOOL_SELECTOR_ALWAYS_INCLUDE,
    TOOL_SELECTOR_MAX_TOOLS,
    TOOL_SELECTOR_MODEL,
    check_api_key,
    is_tool_selection_enabled,
)
from ..tools import create_map
from .db import get_database

logger = logging.getLogger(__name__)

# Instructions données au modèle léger chargé de présélectionner les outils
# pertinents pour la question de l'utilisateur.
TOOL_SELECTOR_SYSTEM_PROMPT = (
    "Tu sélectionnes les outils les plus pertinents pour répondre à la question "
    "géographique de l'utilisateur (altitude, cadastre, urbanisme, unités "
    "administratives, géocodage, données WFS de la Géoplateforme, cartographie, "
    "etc.). Choisis uniquement les outils nécessaires à la question courante. "
    "Pour interroger des données WFS, plusieurs étapes peuvent être requises "
    "(recherche de type, description, lecture des objets) : sélectionne alors "
    "l'ensemble des outils gpf_wfs_* concernés."
)


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


def build_middleware() -> list[AgentMiddleware]:
    """Build the agent middleware stack.

    When dynamic tool selection is enabled, a lightweight model first selects the
    most relevant tools for the current turn so that the (verbose) tool schemas are
    not all sent to the main model on every call. The selector runs first
    (outermost) so the retry middleware only sees the reduced tool set.
    """

    middleware: list[AgentMiddleware] = []

    if is_tool_selection_enabled():
        check_api_key(model_name=TOOL_SELECTOR_MODEL)
        logger.info(
            "Enable dynamic tool selection (model=%s, max_tools=%s, always_include=%s)",
            TOOL_SELECTOR_MODEL,
            TOOL_SELECTOR_MAX_TOOLS,
            TOOL_SELECTOR_ALWAYS_INCLUDE,
        )
        selector_model = init_chat_model(TOOL_SELECTOR_MODEL, temperature=0)
        middleware.append(
            LLMToolSelectorMiddleware(
                model=selector_model,
                system_prompt=TOOL_SELECTOR_SYSTEM_PROMPT,
                max_tools=TOOL_SELECTOR_MAX_TOOLS,
                always_include=TOOL_SELECTOR_ALWAYS_INCLUDE,
            )
        )

    middleware.append(
        ToolRetryMiddleware(
            max_retries=0,
            retry_on=(ToolException,),
            on_failure=format_tool_error,
        )
    )

    return middleware


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
            middleware=build_middleware(),
        )

        logger.info(f"Agent created successfully")
        yield agent


@asynccontextmanager
async def get_agent_no_tools() -> AsyncIterator[CompiledStateGraph]:
    """Get an agent without tools to read the history of a thread"""
    async with get_database() as db:
        check_api_key()
        logger.info("Create chat model: %s (temperature=%s)", MODEL_NAME, TEMPERATURE)
        model = init_chat_model(MODEL_NAME, temperature=TEMPERATURE)
        agent = create_agent(
            model=model,
            tools=[],
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



async def get_messages(agent: CompiledStateGraph, thread_id: str) -> AsyncIterator[Any]:
    """Get the history of a thread"""

    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    if 'messages' in state.values:
        messages = state.values['messages']
        for message in messages:
            yield message,state.created_at
