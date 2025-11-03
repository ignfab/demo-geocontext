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

from db import redis_client, get_checkpointer, get_thread_ids

graph = None

async def lifespan(app: FastAPI):
    global graph

    logger.info("Starting up...")

    logger.info("Create checkpointer...")
    checkpointer = await get_checkpointer()
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

app.mount("/front", StaticFiles(directory="front/dist"), name="front")

def to_gradio_message(message):
    """Convertit un message dans un format JSON compatible avec Gradio Chatbot"""
    
    logger.debug(f"to_gradio_message({type(message)} - {message.type})")
    if not hasattr(message, 'content') or not message.content:
        logger.warning(f"to_gradio_message({type(message)}) - no content")
        logger.warning(f"last_message: {message.pretty_print()}")
        return None

    # Extraire le contenu textuel
    text_content = ""
    if isinstance(message.content, str):
        text_content = message.content
    elif isinstance(message.content, list):
        # Extraire le texte des blocks de contenu
        text_parts = []
        for block in message.content:
            if isinstance(block, dict) and block.get('type') == 'text':
                text_parts.append(block.get('text', ''))
            elif isinstance(block, dict) and block.get('type') == 'tool_use':
                # Afficher les appels d'outils de manière lisible
                tool_name = block.get('name', 'unknown')
                tool_args = block.get('input', {})
                text_parts.append(f"🔧 Appel outil: {tool_name}({tool_args})")
        text_content = "\n".join(text_parts)
    else:
        logger.warning(f"to_gradio_message({type(message)}) - unknown content type")
        logger.warning(f"message: {message.pretty_print()}")
        return None

    # Ajouter un nouveau message pour chaque type d'événement
    if message.type == "human":
        return {
            "role": "user", 
            "content": f"{text_content}"
        }
    elif message.type == "ai":
        # Ajouter la réflexion du modèle
        return {
            "role": "assistant", 
            "content": f"{text_content}", 
            #"metadata": {"title": "💭 Réflexion"}
        }
    elif message.type == "tool":
        tool_title = "📊 Résultat outil"
        if "<ol-simple-map" in text_content:
            tool_title = "🗺️ Carte"
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
                "metadata": {"title": tool_title}
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "role": "assistant", 
                "content": f"{text_content}", 
                "metadata": {"title": tool_title}
            }
    else:
        # Autres types de nœuds
        return {
            "role": "assistant", 
            "content": f"[{message.type}] {text_content}"
        }


async def load_conversation_history(thread_id: str):
    """Charge l'historique de la conversation pour un thread_id donné à partir du graph"""
    global graph
    
    if not graph or not thread_id:
        return []
    
    history = []
    try:
        async for message in get_messages(graph, thread_id):
            logger.debug(f"Traitement message: type={getattr(message, 'type', 'unknown')}, content={getattr(message, 'content', 'no content')}")
            gradio_message = to_gradio_message(message)
            if gradio_message:
                history.append(gradio_message)
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

EXPLICATION = f"""
Vous êtes sur un **démonstrateur technique** permettant de tester le MCP [ignfab/geocontext](https://github.com/ignfab/geocontext#readme) qui s'appuie 
sur les services de la Géoplateforme pour répondre à des questions géographiques (voir [ignfab/geocontext - Fonctionnalités](https://github.com/ignfab/geocontext#fonctionnalit%C3%A9s) pour les exemples).

ATTENTION : Ne pas fournir de données sensibles ou personnelles :
- Les questions sont envoyées à un service tiers (LLM) pour être analysées et traitées.
- Tous les messages sont enregistrés pour permettre une analyse des besoins des utilisateurs pour un tel service.
"""

with gr.Blocks(head=head,title="demo-geocontext") as demo:
    explication = gr.Markdown(
        value=EXPLICATION
    )
    chatbot = gr.Chatbot(
        type="messages", 
        label="demo-geocontext",
        show_copy_button=True,
        show_copy_all_button=True,
        resizable=True,
        sanitize_html=False,
    )

    # Component for user message
    msg = gr.Textbox(
        placeholder="Entrez votre message..."
    )
    # State for thread_id (localStorage)
    thread_state = gr.BrowserState(None)
    # Component for sharing link
    share_output = gr.Markdown(value="", visible=True)
    # Button for new discussion
    new_discussion_btn = gr.Button("🆕 Nouvelle discussion", variant="secondary")

    async def initialize_chat(thread_id: str|None):
        """Initialise le chat avec l'historique existant si disponible"""

        logger.info(f"initialize_chat(thread_id={thread_id})")
        history = []

        # if thread_id is empty and not provided, create a new thread
        if thread_id is None or thread_id.strip() == "":
            thread_id = f"thread-{uuid.uuid4().hex}"
            logger.info(f"thread_id not provided, create a new thread : {thread_id}")
            share_link = create_share_link(thread_id)
            return history, thread_id, share_link

        logger.info(f"thread_id provided : {thread_id}, load history")
        share_link = create_share_link(thread_id)
        
        try:
            history = await load_conversation_history(thread_id)
            logger.info(f"Historique chargé pour thread_id={thread_id}: {len(history)} messages")
            return history, thread_id, share_link
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique pour {thread_id}: {e}")
            return [], thread_id, share_link


    demo.load(initialize_chat, inputs=[thread_state], outputs=[
        chatbot, thread_state, share_output
    ])

    def user(user_message: str, thread_id: str, history: list):
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
                        gradio_message = to_gradio_message(last_message)
                        if gradio_message is not None:
                            history.append(gradio_message)
                            yield history, thread_id

        # Remove metadata for the final message
        history[-1]["metadata"] = None
        yield history, thread_id

    msg.submit(user, [msg, thread_state, chatbot], [msg, thread_state, chatbot], queue=False).then(
        bot, inputs=[chatbot,thread_state], outputs=[chatbot,thread_state]
    )

    # Mettre à jour le lien de partage quand le thread_state change
    @gr.on(thread_state.change, inputs=[thread_state], outputs=[share_output])
    def create_share_link(thread_id: str):
        """Met à jour le lien de partage basé sur le thread_id"""
        if thread_id and thread_id.strip():
            return f"**Lien de partage :** [/discussion?thread_id={thread_id}](/discussion?thread_id={thread_id})"
        return ""

    @gr.on(new_discussion_btn.click, outputs=[chatbot, thread_state, share_output])
    def reset_thread_id():
        """Réinitialise le thread_id et démarre une nouvelle discussion"""
        new_thread_id = f"thread-{uuid.uuid4().hex}"
        logger.info(f"Nouvelle discussion créée avec thread_id: {new_thread_id}")
        share_link = create_share_link(new_thread_id)
        return [], new_thread_id, share_link


# Chatbot in readonly mode
with gr.Blocks(head=head, title="demo-geocontext (lecture seule)") as demo_share:
    explication = gr.Markdown(
        value=f"Vous êtes sur un **démonstrateur technique** permettant de tester le MCP [ignfab/geocontext](https://github.com/ignfab/geocontext#fonctionnalit%C3%A9s). Vous consultez une discussion en **lecture seule**."
    )
    chatbot = gr.Chatbot(
        type="messages", 
        label="demo-geocontext",
        show_copy_button=True,
        show_copy_all_button=True,
        resizable=True,
        sanitize_html=False
    )

    chatbot_link = gr.Markdown(
        value="Accès au chatbot : [/chatbot](/chatbot)", visible=True
    )

    thread_state = gr.State(None)

    async def initialize_chat(request: gr.Request):
        """Initialise le chat avec l'historique existant si disponible"""

        thread_id = request.query_params.get('thread_id')
        if thread_id is None:
            raise ValueError("thread_id is required")

        try:
            history = await load_conversation_history(thread_id)
            logger.info(f"Historique chargé pour thread_id={thread_id}: {len(history)} messages")
            return history, thread_id
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique pour {thread_id}: {e}")
            return [], thread_id

    demo_share.load(initialize_chat, inputs=[], outputs=[chatbot, thread_state])


@app.get("/")
def redirect_to_gradio():
    return RedirectResponse(url=f"/chatbot")

app = gr.mount_gradio_app(app, demo, path="/chatbot")
app = gr.mount_gradio_app(app, demo_share, path="/discussion")


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


