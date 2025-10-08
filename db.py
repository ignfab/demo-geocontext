import logging
logger = logging.getLogger(__name__)

import os

from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

def str2bool(v: str) -> bool :
  return str(v).lower() in ("yes", "true", "t", "1")

REDIS_ENABLED = str2bool(os.getenv('REDIS_ENABLED', False))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_client = None
if REDIS_ENABLED:
    redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

async def get_checkpointer() -> AsyncRedisSaver|InMemorySaver:
    """Create a checkpointer for short term memory (history)"""

    if redis_client is None:
        return InMemorySaver()

    logger.debug("check redis connexion...")
    try:
        ping_result = await redis_client.ping()
        print(ping_result)
    except Exception as e:
        logger.error(e)
        raise e

    logger.debug("create AsyncRedisSaver...")
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    logger.debug("setup AsyncRedisSaver...")
    await checkpointer.asetup()
    logger.debug("AsyncRedisSaver initialized")
    return checkpointer


async def get_thread_ids(checkpointer: AsyncRedisSaver) -> list[str]:
    """Find thread_ids by inspecting checkpointer"""
    thread_ids = []

    try:
        logger.info("get_thread_ids(checkpointer) ...")
        async for checkpoint_tuple in checkpointer.alist({}):
            config = checkpoint_tuple.config
            if 'configurable' in config and 'thread_id' in config['configurable']:
                thread_id = config['configurable']['thread_id']
                if thread_id and thread_id not in thread_ids:
                    thread_ids.append(thread_id)
    except Exception as e:
        logger.warning(f"Fail to retrieve thread ids from checkpointer: {e}")
    
    logger.debug("get_thread_ids(checkpointer) - sort and return thread_ids...")
    thread_ids.sort()
    return thread_ids
