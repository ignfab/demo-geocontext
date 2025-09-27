import os
import logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("demo_gradio")

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
    
    logger.debug(f"to_gradio_message({node_name} - {type(last_message)})")
    if not hasattr(last_message, 'content') or not last_message.content:
        logger.warning(f"to_gradio_message({node_name} - {type(last_message)}) - no content")
        logger.warning(f"last_message: {last_message.pretty_print()}")
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
    else:
        logger.warning(f"to_gradio_message({node_name} - {type(last_message)}) - unknown content type")
        logger.warning(f"last_message: {last_message.pretty_print()}")
        return None

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
<link rel="stylesheet" href="/front/demo-geocontext.css"></link>
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

        if user_message is None or user_message.strip() == "":
            return "", thread_id, history

        return "", thread_id, history + [{"role": "user", "content": user_message.strip()}]

    async def bot(history: list, thread_id: str):
        user_message = history[-1]['content']

        # required to invoke the graph with short term memory
        config = {"configurable": {"thread_id": thread_id}}
        logging.info(f"bot({thread_id} - {user_message})")
        async for event in graph.astream({"messages": [{"role": "user", "content": user_message}]}, config=config):
            logger.debug("Event:", event)
            
            # Traiter les différents types d'événements
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    messages = node_data["messages"]
                    if messages:
                        last_message = messages[-1] if isinstance(messages, list) else messages
                        gradio_message = to_gradio_message(node_name, last_message)
                        if gradio_message is not None:
                            history.append(gradio_message)
                            yield history, thread_id

        # Remove metadata for the final message
        history[-1]["metadata"] = None
        yield history, thread_id

    msg.submit(user, [msg, thread_state, chatbot], [msg, thread_state, chatbot], queue=False).then(
        bot, inputs=[chatbot,thread_state], outputs=[chatbot,thread_state]
    )
    clear.click(lambda: None, None, chatbot, queue=False)



app = FastAPI()

app.mount("/front", StaticFiles(directory="front/dist"), name="front")
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    logging_level = os.getenv("LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=logging.getLevelName(logging_level))
    logging.info("Demo is running on http://localhost:8000")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        # Configuration pour un arrêt plus rapide
        timeout_keep_alive=5,  # Ferme les connexions keep-alive après 5 secondes
        timeout_graceful_shutdown=10,  # Timeout gracieux de 10 secondes
    )


