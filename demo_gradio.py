import asyncio

import gradio as gr
import random
import time

from agent import build_graph

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
                    messages = node_data["messages"]
                    if messages:
                        last_message = messages[-1] if isinstance(messages, list) else messages
                        print(last_message.pretty_print())
                        
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
    print("Demo is running on http://localhost:7860")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
