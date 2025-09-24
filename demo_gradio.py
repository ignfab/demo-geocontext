import asyncio

import gradio as gr
import random
import time

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model

async def build_graph():
        
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
    return builder.compile()

graph = asyncio.run(build_graph())    

config = {"configurable": {"thread_id": "thread-1"}}

with gr.Blocks() as demo:
    chatbot = gr.Chatbot(type="messages")
    msg = gr.Textbox()
    clear = gr.Button("Clear")

    def user(user_message, history: list):
        return "", history + [{"role": "user", "content": user_message}]

    async def bot(history: list):
        user_message = history[-1]['content']

        response = await graph.ainvoke({"messages": [{"role": "user", "content": user_message}]}, config=config)
        
        # Récupérer la dernière réponse de l'assistant
        last_message = response["messages"][-1]
        print(last_message.pretty_print())
        content = last_message.content
        
        if content:  # Vérifier que le contenu n'est pas None
            history.append({"role": "assistant", "content": content})
        
        return history

    msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot, chatbot, chatbot
    )
    clear.click(lambda: None, None, chatbot, queue=False)

if __name__ == "__main__":
    demo.launch()