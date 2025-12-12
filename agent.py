import os
import logging
logger = logging.getLogger(__name__)

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

from tools import create_map

# retreive model name from environment variable or use default
MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-3-7-sonnet-latest")
# retrieve temperature from environment variable or use default
TEMPERATURE = int(os.getenv("TEMPERATURE",0))
# ensure that the required environment variable is set for anthropic models
if MODEL_NAME.startswith("anthropic:"):
    if os.getenv("ANTHROPIC_API_KEY", None) is None:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic models")


logger.info(f"Create graph using model: {MODEL_NAME}")
model = init_chat_model(MODEL_NAME, temperature=TEMPERATURE)


async def build_graph(checkpointer=InMemorySaver()) -> CompiledStateGraph:
    """Build the processing graph with model and tools"""

    logger.info("Load tools from MCP servers...")
    
    # Préparer les variables d'environnement pour le proxy
    env = os.environ.copy()
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]
    proxy_env = {var: env[var] for var in proxy_vars if var in env}
    log_level = env.get("GEOCONTEXT_LOG_LEVEL", "error")

    client = MultiServerMCPClient(
        {
            "geocontext": {
                "command": "npx",
                "args": ["-y", "@ignfab/geocontext"],
                "transport": "stdio",
                "env": {**proxy_env, "LOG_LEVEL": log_level} if proxy_env else {"LOG_LEVEL": log_level}
            },
            "time": {
                "command": "uvx",
                "args": ["mcp-server-time"],
                "transport": "stdio",
                "env": proxy_env if proxy_env else None
            }
        }
    )
    tools = await client.get_tools()
    logger.info(f"Loaded {len(tools)} tools")

    logger.info("Add demo specific tools...")
    tools.append(create_map)

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
    
    # build the graph with short term memory
    logger.info(f"Build graph (checkpointer: {type(checkpointer)})")
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("Graph created successfully")
    return graph



async def get_messages(graph: CompiledStateGraph, thread_id: str):
    """Get the history of a thread"""

    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    if 'messages' in state.values:
        messages = state.values['messages']
        for message in messages:
            yield message,state.created_at
