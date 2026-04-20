import json
import logging
import re
import gradio as gr

logger = logging.getLogger(__name__)

# TODO: This is a very hacky way to remove map HTML from assistant messages.
# We should ideally have a better way to separate map content from text content in the message structure.
_MAP_TAG_RE = re.compile(
    r"<ol-simple-map\b[^>]*>(?:\s*</ol-simple-map>)?",
    flags=re.IGNORECASE | re.DOTALL,
)


def to_gradio_message(message):
    """Convert a message to a dict shape compatible with the Gradio Chatbot."""

    logger.debug(f"to_gradio_message({type(message)} - {message.type})")
    if not hasattr(message, "content") or not message.content:
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
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, dict) and block.get("type") == "tool_use":
                # Afficher les appels d'outils de manière lisible
                tool_name = block.get("name", "unknown")
                tool_args = block.get("input", {})
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
            "content": f"{text_content}",
        }
    elif message.type == "ai":
        # TODO : A dirty hack for now to avoid showing raw map HTML in assistant text. 
        # We should ideally have a better way to separate map content from text content in the message structure.
        cleaned_text = _MAP_TAG_RE.sub("", text_content).strip()
        if cleaned_text == "":
            return None
        return {
            "role": "assistant",
            "content": f"{cleaned_text}",
            # "metadata": {"title": "💭 Réflexion"}
        }
    elif message.type == "tool":
        # Si c'est une carte, l'afficher dans un bloc dédié
        if "<ol-simple-map" in text_content:
            return {
                "role": "assistant",
                "content": gr.HTML(text_content),
                "metadata": {"title": "🗺️ Carte"},
            }

        tool_title = "📊 Résultat outil"
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
                "metadata": {"title": tool_title},
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "role": "assistant",
                "content": f"{text_content}",
                "metadata": {"title": tool_title},
            }
    else:
        # Autres types de nœuds
        return {
            "role": "assistant",
            "content": f"[{message.type}] {text_content}",
        }
