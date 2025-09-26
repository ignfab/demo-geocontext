import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

# retreive model name from environment variable or use default
MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-3-5-sonnet-latest")
# ensure that the required environment variable is set for anthropic models
if MODEL_NAME.startswith("anthropic:"):
    if os.getenv("ANTHROPIC_API_KEY", None) is None:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic models")

async def build_graph():
    """Build the processing graph with model and tools"""
    
    print(f"Create graph using model: {MODEL_NAME}")
    model = init_chat_model(MODEL_NAME)

    print("Load tools from MCP servers...")
    
    # Préparer les variables d'environnement pour le proxy
    env = os.environ.copy()
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]
    proxy_env = {var: env[var] for var in proxy_vars if var in env}
    
    client = MultiServerMCPClient(
        {
            "geocontext": {
                "command": "npx",
                "args": ["-y", "@mborne/geocontext"],
                "transport": "stdio",
                "env": proxy_env if proxy_env else None
            }
        }
    )
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools")

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
    memory = InMemorySaver()
    graph = builder.compile(checkpointer=memory)
    print("Graph created successfully")
    return graph

