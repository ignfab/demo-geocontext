import logging
import asyncio
logger = logging.getLogger(__name__)

import os

from redis.asyncio import Redis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

async def get_redis_checkpointer() -> AsyncRedisSaver:
    """Create a redis checkpointer"""
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.asetup()
    return checkpointer


async def get_thread_ids(checkpointer: AsyncRedisSaver) -> list[str]:
    thread_ids = []

    # Utiliser alist() qui fonctionne avec AsyncRedisSaver
    try:
        async for checkpoint_tuple in checkpointer.alist({}):
            config = checkpoint_tuple.config
            if 'configurable' in config and 'thread_id' in config['configurable']:
                thread_id = config['configurable']['thread_id']
                if thread_id and thread_id not in thread_ids:
                    thread_ids.append(thread_id)
    except Exception as e:
        logger.warning(f"Fail to retrieve thread ids from checkpointer: {e}")
    
    thread_ids.sort()
    return thread_ids
