from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from db import redis_client, get_thread_ids

async def main():
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.asetup()

    thread_ids = await get_thread_ids(checkpointer)
    print(thread_ids)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
