import asyncio

from agent import build_graph

async def stream_graph_updates(user_input: str):
    graph = await build_graph()
    config = {"configurable": {"thread_id": "thread-1"}}
    
    async for event in graph.astream({"messages": [{"role": "user", "content": user_input}]}, config=config):
        # print("Event:", event)
        
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
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            return 0
        await stream_graph_updates(user_input)
    except Exception as e:
        print(f"Erreur: {e}")
        return 1

if __name__ == "__main__":
    asyncio.run(main())



