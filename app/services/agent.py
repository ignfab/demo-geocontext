import logging
from typing import Any, AsyncIterator

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from ..config import MODEL_NAME, TEMPERATURE, check_api_key
from ..tools import create_map
from .mcp_client import get_mcp_tools

logger = logging.getLogger(__name__)

_chat_model: Any | None = None


def _get_chat_model() -> Any:
    global _chat_model
    if _chat_model is None:
        check_api_key()
        logger.info("Create chat model: %s (temperature=%s)", MODEL_NAME, TEMPERATURE)
        _chat_model = init_chat_model(MODEL_NAME, temperature=TEMPERATURE)
    return _chat_model


async def get_agent(*, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Construit le graphe LangGraph avec le modèle, les outils MCP et la mémoire."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    logger.info("Load tools from MCP servers...")
    tools = await get_mcp_tools()
    logger.info("Loaded %s tools", len(tools))

    logger.info("Add demo specific tools...")
    tools.append(create_map)

    model = _get_chat_model()

    async def call_model(state: MessagesState):
        response = await model.bind_tools(tools).ainvoke(state["messages"])
        return {"messages": response}

    builder = StateGraph(MessagesState)
    builder.add_node(call_model)
    builder.add_node(ToolNode(tools))
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
    )
    builder.add_edge("tools", "call_model")

    logger.info("Build graph (checkpointer: %s)", type(checkpointer))
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("Graph created successfully")
    return graph


async def get_messages(graph: CompiledStateGraph, thread_id: str) -> AsyncIterator[Any]:
    """Itère sur l'historique des messages d'un thread."""
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)

    if "messages" in state.values:
        messages = state.values["messages"]
        for message in messages:
            yield message
