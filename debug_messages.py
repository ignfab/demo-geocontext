import sys

from agent import build_graph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from db import redis_client


async def main():
    # read thread_id from command line or use default
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
    else:
        thread_id = "thread-b70ddfa45fcf469bbb202c75b860e0aa"

    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.asetup()
    
    graph = await build_graph(checkpointer=checkpointer)
    
    async for message in get_messages(graph, thread_id):
        print(message.pretty_print())
        print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    


