import os
import logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("demo_cli")

import asyncio

from agent import build_graph

async def stream_graph_updates(graph, user_input: str):
    
    config = {"configurable": {"thread_id": "thread-1"}}
    
    async for event in graph.astream({"messages": [{"role": "user", "content": user_input}]}, config=config):
        # Traiter les différents types d'événements
        for node_name, node_data in event.items():
            if "messages" in node_data:
                messages = node_data["messages"]
                if messages:
                    last_message = messages[-1] if isinstance(messages, list) else messages
                    print(last_message.pretty_print())
                    print("")

async def main():
    try:
        print("Loading graph, please wait...")
        graph = await build_graph()
        # loop prompt until user wants to exit
        print("Welcome to the demo-geocontext CLI! Type a message and press Enter to send it. Use 'quit', 'exit', or 'q' to exit.")
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            return 0
        await stream_graph_updates(graph, user_input)
    except Exception as e:
        print(f"Erreur: {e}")
        return 1

if __name__ == "__main__":
    asyncio.run(main())



