import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-3-5-sonnet-latest")

async def build_graph():
    print(f"Create graph using model: {MODEL_NAME}")
    model = init_chat_model(MODEL_NAME)

    print("Load tools from MCP servers...")
    client = MultiServerMCPClient(
        {
            "geocontext": {
                "command": "npx",
                "args": ["-y", "@mborne/geocontext"],
                "transport": "stdio",
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
    memory = InMemorySaver()
    graph = builder.compile(checkpointer=memory)
    print("Graph created successfully")
    return graph

