import asyncio
import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model

async def main():
    model = init_chat_model("anthropic:claude-3-5-sonnet-latest")

    client = MultiServerMCPClient(
        {
            "geocontext": {
                "command": "npx",
                # Make sure to update to the full absolute path to your math_server.py file
                "args": ["-y", "@mborne/geocontext"],
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()

    def call_model(state: MessagesState):
        response = model.bind_tools(tools).invoke(state["messages"])
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
    graph = builder.compile()

    config = {"configurable": {"thread_id": "thread-1"}}
    response = await graph.ainvoke({"messages": "Quelle est l'altitude de la mairie de Loray?"})
    for message in response["messages"]:
        print(message.pretty_print())

if __name__ == "__main__":
    asyncio.run(main())
