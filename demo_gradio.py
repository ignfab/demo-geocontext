import asyncio

import gradio as gr
import random
import time

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

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
    memory = InMemorySaver()
    return builder.compile(checkpointer=memory)

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
        
        async for event in graph.astream({"messages": [{"role": "user", "content": user_message}]}, config=config):
            print("Event:", event)
            
            # Traiter les différents types d'événements
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    print("=======================================================================")
                    print("=======================================================================")
                    print("=======================================================================")
                    messages = node_data["messages"]
                    if messages:
                        last_message = messages[-1] if isinstance(messages, list) else messages
                        print(f"Node {node_name}:")
                        print(last_message.pretty_print())
                        print("=======================================================================")
                        print(f"message={last_message.pretty_repr()}")
                        print("=======================================================================")
                        
                        # Créer un nouveau message pour chaque événement
                        if hasattr(last_message, 'content') and last_message.content:
                            # Extraire le contenu textuel
                            text_content = ""
                            if isinstance(last_message.content, str):
                                text_content = last_message.content
                            elif isinstance(last_message.content, list):
                                # Extraire le texte des blocks de contenu
                                text_parts = []
                                for block in last_message.content:
                                    if isinstance(block, dict) and block.get('type') == 'text':
                                        text_parts.append(block.get('text', ''))
                                    elif isinstance(block, dict) and block.get('type') == 'tool_use':
                                        # Afficher les appels d'outils de manière lisible
                                        tool_name = block.get('name', 'unknown')
                                        tool_args = block.get('input', {})
                                        text_parts.append(f"🔧 Appel outil: {tool_name}({tool_args})")
                                text_content = "\n".join(text_parts)
                            
                            if text_content:
                                # Ajouter un nouveau message pour chaque type d'événement
                                if node_name == "call_model":
                                    # Ajouter la réflexion du modèle
                                    history.append({
                                        "role": "assistant", 
                                        "content": f"{text_content}", 
                                        "metadata": {"title": "💭 Réflexion"}
                                    })
                                elif node_name == "tools":
                                    # Ajouter les résultats des outils
                                    history.append({"role": "assistant", "content": f"{text_content}", "metadata": {"title": "📊 Résultat outil"}})
                                else:
                                    # Autres types de nœuds
                                    history.append({"role": "assistant", "content": f"[{node_name}] {text_content}"})
                                
                                yield history

        # Remove metadata for the last message
        history[-1]["metadata"] = None
        yield history

    msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot, chatbot, chatbot
    )
    clear.click(lambda: None, None, chatbot, queue=False)

if __name__ == "__main__":
    demo.launch()