import json
import os
from typing import Any

MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-6")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.0))
if TEMPERATURE < 0 or TEMPERATURE > 1:
    raise ValueError("TEMPERATURE must be between 0 and 1")

# Dynamic tool selection: a lightweight model selects the most relevant tools for
# each turn so that the verbose tool schemas (notably the gpf_wfs_* family) are not
# all sent to the main model on every call. Set TOOL_SELECTOR_MODEL to an empty
# string (or "none") to disable the feature and send every tool to the main model.
TOOL_SELECTOR_MODEL = os.getenv("TOOL_SELECTOR_MODEL", "anthropic:claude-haiku-4-5")
TOOL_SELECTOR_MAX_TOOLS = int(os.getenv("TOOL_SELECTOR_MAX_TOOLS", "5"))
if TOOL_SELECTOR_MAX_TOOLS < 1:
    raise ValueError("TOOL_SELECTOR_MAX_TOOLS must be greater than or equal to 1")
# Tools always exposed to the main model, regardless of the selection. They do not
# count against TOOL_SELECTOR_MAX_TOOLS.
TOOL_SELECTOR_ALWAYS_INCLUDE = [
    name.strip()
    for name in os.getenv("TOOL_SELECTOR_ALWAYS_INCLUDE", "create_map,geocode").split(",")
    if name.strip()
]


def is_tool_selection_enabled() -> bool:
    """Return whether dynamic tool selection is enabled."""
    return TOOL_SELECTOR_MODEL.strip().lower() not in ("", "none")


# 
DB_URI = os.getenv("DB_URI", None)


def check_api_key(*, model_name: str | None = None) -> None:
    """Raise if the model requires an API key that is missing from the environment."""
    name = MODEL_NAME if model_name is None else model_name
    if name.startswith("anthropic:") and os.getenv("ANTHROPIC_API_KEY", None) is None:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic models")


def _proxy_env() -> dict[str, str]:
    proxy_vars = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
    return {var: os.environ[var] for var in proxy_vars if var in os.environ}


def get_mcp_servers_config() -> dict[str, dict[str, Any]]:
    """MCP server configuration for MultiServerMCPClient.

    If MCP_SERVERS_CONFIG_PATH is set, the JSON file at that path is loaded and
    returned directly, overriding the built-in defaults.
    """
    config_path = os.environ.get("MCP_SERVERS_CONFIG_PATH", None)
    if config_path is not None:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    proxy = _proxy_env()
    log_level = os.environ.get("GEOCONTEXT_LOG_LEVEL", "error")
    geocontext_env = {"LOG_LEVEL": log_level, **proxy}
    return {
        "geocontext": {
            "command": "npx",
            "args": ["-y", "@ignfab/geocontext"],
            "transport": "stdio",
            "env": geocontext_env,
        },
        "time": {
            "command": "uvx",
            "args": ["mcp-server-time"],
            "transport": "stdio",
            "env": proxy if proxy else None,
        },
    }
