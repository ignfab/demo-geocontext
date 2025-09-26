from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

import uuid
import asyncio
import json

import gradio as gr

from agent import build_graph

graph = asyncio.run(build_graph())

def to_gradio_message(node_name, last_message):
    """Convertit un message en format compatible avec Gradio"""
    
    print(f"to_gradio_message({node_name} - {type(last_message)})")
    if not hasattr(last_message, 'content') or not last_message.content:
        return None

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

    # Ajouter un nouveau message pour chaque type d'événement
    if node_name == "call_model":
        # Ajouter la réflexion du modèle
        return {
            "role": "assistant", 
            "content": f"{text_content}", 
            "metadata": {"title": "💭 Réflexion"}
        }
    elif node_name == "tools":
        # Si c'est du HTML (contient des balises HTML), l'afficher directement
        if "<ol-simple-map" in text_content or "<ol-map" in text_content:
            return {
                "role": "assistant", 
                "content": f"{text_content}", 
                "metadata": {"title": "🗺️ Carte"}
            }
        # Si c'est du JSON valide, le formater avec coloration syntaxique
        try:
            parsed_json = json.loads(text_content)
            formatted_json = json.dumps(parsed_json, indent=2, ensure_ascii=False)
            content = f"Réponse JSON :\r\n ```json\n{formatted_json}\n```"
            return {
                "role": "assistant", 
                "content": f"{content}", 
                "metadata": {"title": "📊 Résultat outil"}
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "role": "assistant", 
                "content": f"{text_content}", 
                "metadata": {"title": "📊 Résultat outil"}
            }
    else:
        # Autres types de nœuds
        return {
            "role": "assistant", 
            "content": f"[{node_name}] {text_content}"
        }


# https://openlayers-elements.netlify.app/
head = f"""
<script src="/front/demo-geocontext.min.js"></script>
<link rel="stylesheet" src="/front/demo-geocontext.css"></link>
"""


with gr.Blocks(head=head) as demo:
    chatbot = gr.Chatbot(
        type="messages", 
        label="demo-geocontext",
        show_copy_button=True,
        show_copy_all_button=True,
        resizable=True,
        sanitize_html=False,
    )
    msg = gr.Textbox()
    clear = gr.Button("Clear")
    thread_state = gr.State(None)
    
    def user(user_message: str, thread_id: str | None, history: list):
        # première interaction → on attribue un identifiant de session
        if not thread_id:
            thread_id = f"thread-{uuid.uuid4().hex}"

        return "", thread_id, history + [{"role": "user", "content": user_message}]

    async def bot(history: list):
        user_message = history[-1]['content']
        
        # required to invoke the graph with short term memory
        config = {"configurable": {"thread_id": "thread-1"}}
        async for event in graph.astream({"messages": [{"role": "user", "content": user_message}]}, config=config):
            print("Event:", event)
            
            # Traiter les différents types d'événements
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    messages = node_data["messages"]
                    if messages:
                        last_message = messages[-1] if isinstance(messages, list) else messages
                        gradio_message = to_gradio_message(node_name, last_message)
                        if gradio_message is not None:
                            history.append(gradio_message)
                            yield history

        # Remove metadata for the final message
        history[-1]["metadata"] = None
        yield history

    msg.submit(user, [msg, thread_state, chatbot], [msg, thread_state, chatbot], queue=False).then(
        bot, chatbot, chatbot
    )
    clear.click(lambda: None, None, chatbot, queue=False)



app = FastAPI()

app.mount("/front", StaticFiles(directory="front/dist"), name="front")
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("Demo is running on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


