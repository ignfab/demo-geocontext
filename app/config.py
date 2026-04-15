import os
from typing import Any

MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-6")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.0))
if TEMPERATURE < 0 or TEMPERATURE > 1:
    raise ValueError("TEMPERATURE must be between 0 and 1")

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
    """MCP server configuration for MultiServerMCPClient."""
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
