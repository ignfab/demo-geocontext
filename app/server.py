import os
import uuid
import logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

import uvicorn
from fastapi import FastAPI,Request,Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .models import User
from .services.auth import get_current_user
from .services.db import get_database
from urllib.parse import quote as urlib_quote

import gradio as gr
from .services.agent import get_agent, get_messages
from .helpers.gradio import to_gradio_message

def str2bool(v: str) -> bool :
  return str(v).lower() in ("yes", "true", "t", "1")


# the graph instance
graph = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph

    logger.info("Starting up...")
    async with get_agent() as g:
        graph = g
        yield
    graph = None
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

@app.get('/me')
async def me(
    user: User = Depends(get_current_user)
) -> User :
    return user

@app.get('/health')
async def health():
    return {"status": "ok", "message": "app is running"}

@app.get('/health/db')
async def health_redis():
    try:
        db = get_database()
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "database is not ready"},
        )

    healthy = await db.is_healthy()
    if healthy:
        return {"status": "ok", "message": "connected"} 
    else:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "database is disconnected"},
        )

# ol-simple-map
app.mount("/front", StaticFiles(directory="front/dist"), name="front")
# logos
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


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
HTML_HEAD = f"""
<script src="/front/demo-geocontext.min.js"></script>
<link rel="stylesheet" href="/front/demo-geocontext.css"></link>
<link rel="stylesheet" href="/assets/gradio.css"></link>
"""

CONTACT_EMAIL=os.getenv("CONTACT_EMAIL", "dev@localhost")
CONTACT_SUBJECT="[demo-geocontext] Message de contact"
CONTACT_BODY="""
Merci de remplacer ce texte par votre message en incluant le lien de partage de la discussion si nécessaire.
"""

HTML_FOOTER=f"""
<div style='text-align:center; margin-top: 20px;'>
    <a href="/mentions-legales" target="_blank">
        Mentions légales
    </a>
    |
    <a title="{CONTACT_EMAIL}" href="mailto:{CONTACT_EMAIL}?subject={urlib_quote(CONTACT_SUBJECT)}&body={urlib_quote(CONTACT_BODY)}" target="_blank">
        Nous contacter
    </a>
</div>
"""

HTML_HEADER="""
<div class="demo-header">
    <div class="logo-container">
        <a href="https://www.ign.fr/" title="Institut national de l'information géographique et forestière" target="_blank">
            <img src="/assets/logo-ign.png" alt="IGN"/>
        </a>
    </div>
    <div class="info-container">
        Ce chatbot est une expérimentation conçue par les équipes de l’<a href="https://www.ign.fr" title="Institut national de l'information géographique et forestière" target="_blank">IGN</a>. Il facilite l’exploration 
        et l’utilisation des services de la Géoplateforme, en s’appuyant sur le serveur MCP <a href="https://github.com/ignfab/geocontext#readme" target="_blank">ignfab/geocontext</a>, également développé par l’IGN.    
    </div>
</header>
"""


EXPLANATION_DEMO = f"""
Utilisez le champ de texte pour poser vos questions géographiques en langage naturel. Pour des exemples de requêtes, 
consultez la section « Fonctionnalités » de [ignfab/geocontext - Fonctionnalités](https://github.com/ignfab/geocontext#fonctionnalit%C3%A9s).

Ce service est utilisable uniquement avec un compte geoplateforme. <b>Tous vos messages et questions sont enregistrés pour raison de sécurité.</b>

<details>
<summary>ATTENTION : <b>Ne pas fournir de données sensibles ou personnelles dans les messages</b></summary>

- Les questions sont envoyées à un service tiers (LLM) pour être analysées et traitées.
- Tous les messages sont enregistrés pour permettre une analyse des besoins des utilisateurs pour un tel service.
</details>
"""


with gr.Blocks(head=HTML_HEAD,title="demo-geocontext") as demo:
    # Logo and header description
    header = gr.Markdown(value=HTML_HEADER)
    # demo explanation
    explanation = gr.Markdown(
        value=EXPLANATION_DEMO
    )
    # Component for chatbot display
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
    # State for username
    username_state = gr.State(None)
    # Component for sharing link
    share_output = gr.Markdown(value="", visible=True)
    # Button for new discussion
    new_discussion_btn = gr.Button("🆕 Nouvelle discussion", variant="secondary")
    # Footer with legal mentions link
    footer = gr.Markdown(value=HTML_FOOTER)

    async def initialize_chat(request: gr.Request, thread_id: str|None):
        """Initialise le chat avec l'historique existant si disponible"""

        username = request.username    
            
        history = []

        # if thread_id is empty and not provided, create a new thread
        if thread_id is None or thread_id.strip() == "":
            thread_id = f"thread-{uuid.uuid4().hex}"
            logger.info(f"initialize_chat(thread_id={thread_id}, username={username}) : new thread created")
            share_link = create_share_link(thread_id)
            return history, username, thread_id, share_link

        logger.info(f"initialize_chat(thread_id={thread_id}, username={username}) : thread_id provided, loading history...")
        share_link = create_share_link(thread_id)
        try:
            history = await load_conversation_history(thread_id)
            logger.info(f"initialize_chat(thread_id={thread_id}, username={username}) : history loaded with {len(history)} message(s)")
            return history, username, thread_id, share_link
        except Exception as e:
            logger.error(f"initialize_chat(thread_id={thread_id}, username={username}) : error loading history for thread_id : {e}")
            return [], username, thread_id, share_link


    demo.load(initialize_chat, inputs=[thread_state], outputs=[
        chatbot, username_state, thread_state, share_output
    ])

    def user(user_message: str, thread_id: str, username: str, history: list):
        """handle user message and append it to history"""

        if user_message is None or user_message.strip() == "":
            return "", history

        message_content = user_message.strip()
        logger.info(f"user({thread_id}, {username}): {message_content}")
        return "", history + [{"role": "user", "content": message_content}]

    async def bot(history: list, thread_id: str):
        """answer the last user message in history by invoking the agent"""

        global graph
        
        # retrieve the last user message
        user_message = history[-1]['content']

        # required to invoke the graph with short term memory
        config = {"configurable": {"thread_id": thread_id}}
        logger.debug(f"bot({thread_id} - {user_message})")
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
                            yield history

        # Remove metadata for the final message
        history[-1]["metadata"] = None
        yield history

    msg.submit(user, [msg, thread_state, username_state, chatbot], [msg, chatbot], queue=False).then(
        bot, inputs=[chatbot,thread_state], outputs=[chatbot]
    )

    @gr.on(thread_state.change, inputs=[thread_state], outputs=[share_output])
    def create_share_link(thread_id: str):
        """Update share link on change for thread_id"""
        if thread_id and thread_id.strip():
            return f"**Lien de partage :** [/discussion?thread_id={thread_id}](/discussion?thread_id={thread_id})"
        return ""

    @gr.on(new_discussion_btn.click, inputs=[username_state], outputs=[chatbot, thread_state, share_output])
    def reset_thread_id(username: str):
        """Reset thread_id to start a new conversation"""

        new_thread_id = f"thread-{uuid.uuid4().hex}"
        logger.info(f"reset_thread_id(username={username}, new_thread_id={new_thread_id})")
        share_link = create_share_link(new_thread_id)
        return [], new_thread_id, share_link


# Chatbot in readonly mode

EXPLANATION_DEMO_SHARE = f"""
Vous consultez une discussion en lecture seule.
"""

with gr.Blocks(head=HTML_HEAD, title="demo-geocontext (lecture seule)") as demo_share:
    # Logo and header description
    header = gr.Markdown(value=HTML_HEADER)
    # demo explanation
    explanation = gr.Markdown(
        value=EXPLANATION_DEMO_SHARE
    )
    # Component for chatbot display
    chatbot = gr.Chatbot(
        type="messages", 
        label="demo-geocontext",
        show_copy_button=True,
        show_copy_all_button=True,
        resizable=True,
        sanitize_html=False
    )
    # Link to chatbot main page
    chatbot_link = gr.Markdown(
        value="Accès au chatbot : [/chatbot](/chatbot)", visible=True
    )
    # Footer with legal mentions link
    footer = gr.Markdown(value=HTML_FOOTER)

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


# Yes... This is an abusive reuse of Gradio to serve a static markdown page :)
# load pages/mentions-legales.md
MENTION_LEGALES_PATH="pages/mentions-legales.md"
with gr.Blocks(head=HTML_HEAD, title="demo-geocontext - mentions légales") as mentions_legales:
    # Logo and header description
    header = gr.Markdown(value=HTML_HEADER)

    with open(MENTION_LEGALES_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
        md = gr.Markdown(
            value=md_content
        )

@app.get("/")
def redirect_to_gradio():
    return RedirectResponse(url=f"/chatbot")

def get_gradio_user(request: Request):
    """Retrieve user for Gradio (available as request.username)"""

    user = get_current_user(request)
    # TODO: check groups if needed and available in token
    return user.email

app = gr.mount_gradio_app(app, demo, path="/chatbot", auth_dependency=get_gradio_user, show_api=False)
app = gr.mount_gradio_app(app, demo_share, path="/discussion", show_api=False)
app = gr.mount_gradio_app(app, mentions_legales, path="/mentions-legales", show_api=False)

class HealthCheckFilter(logging.Filter):
    """Remove /health and /health/* from application server logs"""
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


if __name__ == "__main__":
    logger.info("Demo is running on http://localhost:8000")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        # Configuration pour un arrêt plus rapide
        timeout_keep_alive=5,  # Ferme les connexions keep-alive après 5 secondes
        timeout_graceful_shutdown=10,  # Timeout gracieux de 10 secondes
    )

