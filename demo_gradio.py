import os
import uuid
import json
import logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("demo_gradio")

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import gradio as gr

from agent import build_graph, get_messages

from db import redis_client, get_thread_ids, get_redis_checkpointer

graph = None

async def lifespan(app: FastAPI):
    global graph

    logger.info("Starting up...")

    logger.info("Create checkpointer...")
    checkpointer = await get_redis_checkpointer()
    logger.info("Build graph...")
    graph = await build_graph(checkpointer=checkpointer)
    yield
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan)

@app.get('/health')
async def health():
    return {"status": "ok", "message": "app is running"}

@app.get('/health/redis')
async def health_redis():
    try:
        await redis_client.ping()
        return {"status": "ok", "message": "connected"} 
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "redis is disconnected"},
        )

@app.get('/admin/threads')
async def admin_thread_ids():
    global graph
    thread_ids = await get_thread_ids(graph.checkpointer)
    return {"status": "ok", "thread_ids": thread_ids}


app.mount("/front", StaticFiles(directory="front/dist"), name="front")


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
            content = f"""
<details>
<summary>📊 Réponse JSON</summary>

```json
{formatted_json}
```
</details>
                """

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


async def load_conversation_history(thread_id: str):
    """Charge l'historique de la conversation depuis Redis pour un thread_id donné"""
    global graph
    
    if not graph or not thread_id:
        return []
    
    history = []
    try:
        async for message in get_messages(graph, thread_id):
            logger.debug(f"Traitement message: type={getattr(message, 'type', 'unknown')}, content={getattr(message, 'content', 'no content')}")
            
            if hasattr(message, 'type'):
                if message.type == 'human':
                    # Message utilisateur
                    content = message.content if isinstance(message.content, str) else str(message.content)
                    history.append({"role": "user", "content": content})
                elif message.type == 'ai':
                    # Message assistant - utiliser la fonction existante de conversion
                    gradio_message = to_gradio_message("call_model", message)
                    if gradio_message:
                        history.append(gradio_message)
                elif message.type == 'tool':
                    # Message d'outil - utiliser la fonction existante de conversion
                    gradio_message = to_gradio_message("tools", message)
                    if gradio_message:
                        history.append(gradio_message)
                else:
                    logger.debug(f"Type de message non géré: {message.type}")
            else:
                logger.debug(f"Message sans attribut 'type': {type(message)}")
    except Exception as e:
        logger.error(f"Erreur lors du chargement de l'historique pour {thread_id}: {e}")
        raise
    
    logger.info(f"Historique chargé: {len(history)} messages pour thread_id={thread_id}")
    return history


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
    explication = gr.Markdown(value='Ceci est un démonstrateur')
    msg = gr.Textbox()
    thread_state = gr.State(None)
    
    async def initialize_chat(request: gr.Request):
        """Initialise le chat avec l'historique existant si disponible"""
        thread_id = request.query_params.get('thread_id')
        if thread_id:
            try:
                history = await load_conversation_history(thread_id)
                logger.info(f"Historique chargé pour thread_id={thread_id}: {len(history)} messages")
                return history, thread_id
            except Exception as e:
                logger.error(f"Erreur lors du chargement de l'historique pour {thread_id}: {e}")
                return [], thread_id
        logger.info("Nouveau thread - pas d'historique à charger")
        return [], None
    
    
    def user(user_message: str, thread_id: str | None, history: list, request: gr.Request):
        # Récupérer le thread_id depuis les paramètres de l'URL
        thread_id = request.query_params.get('thread_id')
        
        if not thread_id:
            raise ValueError("thread_id manquant dans l'URL")

        if user_message is None or user_message.strip() == "":
            return "", thread_id, history

        return "", thread_id, history + [{"role": "user", "content": user_message.strip()}]

    async def bot(history: list, thread_id: str):
        global graph
        
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

    
    # Charger l'historique au démarrage
    demo.load(initialize_chat, inputs=[], outputs=[chatbot, thread_state])
    
    msg.submit(user, [msg, thread_state, chatbot], [msg, thread_state, chatbot], queue=False).then(
        bot, inputs=[chatbot,thread_state], outputs=[chatbot,thread_state]
    )


@app.get("/")
def redirect_to_gradio():
    thread_id = f"thread-{uuid.uuid4().hex}"
    return RedirectResponse(url=f"/chatbot?thread_id={thread_id}")

app = gr.mount_gradio_app(app, demo, path="/chatbot")

if __name__ == "__main__":
    logging.info("Demo is running on http://localhost:8000")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        # Configuration pour un arrêt plus rapide
        timeout_keep_alive=5,  # Ferme les connexions keep-alive après 5 secondes
        timeout_graceful_shutdown=10,  # Timeout gracieux de 10 secondes
    )


