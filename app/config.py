import os

MODEL_NAME = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-6")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.0))

if MODEL_NAME.startswith("anthropic:"):
    if os.getenv("ANTHROPIC_API_KEY", None) is None:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required for anthropic models")
    if TEMPERATURE < 0 or TEMPERATURE > 1:
        raise ValueError("TEMPERATURE must be between 0 and 1")
