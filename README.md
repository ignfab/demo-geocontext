# demo-geocontext

Interactive demo for [mborne/geocontext](https://github.com/mborne/geocontext#readme) based on [Gradio - ChatBot](https://www.gradio.app/guides/creating-a-chatbot-fast) and  [LangGraph](https://langchain-ai.github.io/langgraph/agents/mcp/#use-mcp).

## Screenshot

![Screenshot](img/screenshot.png)

## Requirements

* [uv](https://github.com/astral-sh/uv#installation) ( Python package and project manager )
* [NodeJS (npx)](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)


## Parameters

| Name              | Description                                                                                                                          | Default                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| MODEL_NAME        | The name of the model (see [LangGraph - create_react_agent](https://langchain-ai.github.io/langgraph/agents/models/#use-in-an-agent) | "anthropic:claude-3-5-sonnet-latest" |
| ANTHROPIC_API_KEY | Required from `anthropic:*` models                                                                                                   |                                      |

> Note that "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY" are supported if you have to use a corporate proxy


## Usage

With uv on Linux :

```bash
# download repository
git clone https://github.com/mborne/demo-geocontext
cd demo-geocontext

# configure model model and credentials
export MODEL_NAME="anthropic:claude-3-5-sonnet-latest"
export ANTHROPIC_API_KEY="YourApiKey"

# start gradio demo on http://localhost:7860/ :
uv run demo_gradio.py
```

With uv on Windows, adapt model and credentials configuration as follow :

```powershell
$env:MODEL_NAME="ollama:mistral:7b"
$env:ANTHROPIC_API_KEY="YourApiKey"
```


## Credits

* [gradio - Chatbot](https://www.gradio.app/docs/gradio/chatbot)
* [LangGraph](https://langchain-ai.github.io/langgraph/agents/mcp/#use-mcp) and [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters#readme)
* [Plotting MCP Server](https://github.com/StacklokLabs/plotting-mcp)

* https://openlayers-elements.netlify.app/

## License

[MIT](./LICENSE)
