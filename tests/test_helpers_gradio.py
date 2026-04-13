"""Tests for app.helpers.gradio.to_gradio_message."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.helpers.gradio import to_gradio_message


def _message(msg_type: str, content, pretty: str = "") -> SimpleNamespace:
    def pretty_print() -> str:
        return pretty or repr(content)

    return SimpleNamespace(type=msg_type, content=content, pretty_print=pretty_print)


def test_to_gradio_message_returns_none_when_no_content() -> None:
    assert to_gradio_message(_message("human", "")) is None
    assert to_gradio_message(_message("human", [])) is None


def test_to_gradio_message_human_string() -> None:
    out = to_gradio_message(_message("human", "Hello"))
    assert out == {"role": "user", "content": "Hello"}


def test_to_gradio_message_ai_string() -> None:
    out = to_gradio_message(_message("ai", "Hi there"))
    assert out == {"role": "assistant", "content": "Hi there"}


def test_to_gradio_message_list_text_and_tool_use() -> None:
    content = [
        {"type": "text", "text": "Part one"},
        {"type": "tool_use", "name": "search", "input": {"q": "x"}},
    ]
    out = to_gradio_message(_message("ai", content))
    assert out["role"] == "assistant"
    assert "Part one" in out["content"]
    assert "🔧 Appel outil: search" in out["content"]
    assert "{'q': 'x'}" in out["content"] or '"q": "x"' in out["content"]


def test_to_gradio_message_tool_json_wraps_in_details() -> None:
    payload = {"ok": True, "n": 1}
    out = to_gradio_message(_message("tool", json.dumps(payload)))
    assert out["role"] == "assistant"
    assert out["metadata"]["title"] == "📊 Résultat outil"
    assert "<details>" in out["content"]
    assert "```json" in out["content"]
    assert '"ok": true' in out["content"]


def test_to_gradio_message_tool_non_json_plain() -> None:
    out = to_gradio_message(_message("tool", "not json {}"))
    assert out == {
        "role": "assistant",
        "content": "not json {}",
        "metadata": {"title": "📊 Résultat outil"},
    }


def test_to_gradio_message_tool_map_title_when_ol_tag() -> None:
    text = json.dumps({"html": "<ol-simple-map />"})
    out = to_gradio_message(_message("tool", text))
    assert out["metadata"]["title"] == "🗺️ Carte"


def test_to_gradio_message_unknown_node_type() -> None:
    out = to_gradio_message(_message("system", "sys prompt"))
    assert out == {"role": "assistant", "content": "[system] sys prompt"}


def test_to_gradio_message_unknown_content_type_returns_none() -> None:
    out = to_gradio_message(_message("human", 123))
    assert out is None
