import json
import logging
import re

import gradio as gr

logger = logging.getLogger(__name__)

# ``create_map`` map markup: the Chatbot escapes ``<ol-simple-map>`` in Markdown,
# so we extract the block and render it with ``gr.HTML``.
_OL_SIMPLE_MAP_BLOCK = re.compile(
    r"<ol-simple-map\b[^>]*/>|<ol-simple-map\b[^>]*>[\s\S]*?</ol-simple-map>",
    flags=re.IGNORECASE,
)


def _ai_content_for_gradio_chatbot(text: str) -> str | list:
    """Split assistant markdown so ``<ol-simple-map>`` is not escaped.

    The Chatbot renders strings as Markdown, so custom map tags show as literal
    text. Each match from ``_OL_SIMPLE_MAP_BLOCK`` becomes ``gr.HTML(block)``;
    other segments stay plain strings (unchanged Markdown). Returns ``text`` if
    there is nothing to split or the regex matches nothing; otherwise a single
    ``gr.HTML`` or a list alternating strings and ``gr.HTML`` in message order.
    """
    if "<ol-simple-map" not in text.casefold():
        return text
    matches = list(_OL_SIMPLE_MAP_BLOCK.finditer(text))
    if not matches:
        return text
    chunks: list = []
    last_end = 0
    for m in matches:
        before = text[last_end : m.start()]
        if before:
            chunks.append(before)
        chunks.append(gr.HTML(m.group(0)))
        last_end = m.end()
    after = text[last_end:]
    if after:
        chunks.append(after)
    if len(chunks) == 1:
        return chunks[0]
    return chunks


def to_gradio_message(message):
    """Convert a message to a dict shape compatible with the Gradio Chatbot."""

    logger.debug(f"to_gradio_message({type(message)} - {message.type})")
    if not hasattr(message, "content") or not message.content:
        logger.warning(f"to_gradio_message({type(message)}) - no content")
        logger.warning(f"last_message: {message.pretty_print()}")
        return None

    # Extract textual content
    text_content = ""
    if isinstance(message.content, str):
        text_content = message.content
    elif isinstance(message.content, list):
        # Extract text from content blocks
        text_parts = []
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, dict) and block.get("type") == "tool_use":
                # Show tool calls in a readable form
                tool_name = block.get("name", "unknown")
                tool_args = block.get("input", {})
                text_parts.append(f"🔧 Appel outil: {tool_name}({tool_args})")
        text_content = "\n".join(text_parts)
    else:
        logger.warning(f"to_gradio_message({type(message)}) - unknown content type")
        logger.warning(f"message: {message.pretty_print()}")
        return None

    # One chat bubble per LangChain message type
    if message.type == "human":
        return {
            "role": "user",
            "content": f"{text_content}",
        }
    elif message.type == "ai":
        text_stripped = text_content.strip()
        if text_stripped == "":
            return None
        return {
            "role": "assistant",
            "content": _ai_content_for_gradio_chatbot(text_stripped),
        }
    elif message.type == "tool":
        # Map tool: no separate bubble — the LLM pastes the fragment into the next reply.
        if "<ol-simple-map" in text_content:
            return None

        tool_title = "📊 Résultat outil"
        # Pretty-print valid JSON for syntax highlighting in the UI
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
        # Other LangGraph / LangChain node types
        return {
            "role": "assistant",
            "content": f"[{message.type}] {text_content}",
        }
