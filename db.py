import logging
logger = logging.getLogger(__name__)

import os

from langgraph.checkpoint.memory import InMemorySaver

from redis.asyncio import Redis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncConnection
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

def str2bool(v: str) -> bool :
  return str(v).lower() in ("yes", "true", "t", "1")

REDIS_ENABLED = str2bool(os.getenv('REDIS_ENABLED', False))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

POSTGRES_ENABLED = str2bool(os.getenv('POSTGRES_ENABLED', False))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

class BaseDatabase:
    def __init__(self, checkpointer: InMemorySaver|AsyncRedisSaver|AsyncPostgresSaver):
        self.checkpointer = checkpointer
        pass

    async def is_healthy(self) -> bool:
        raise NotImplementedError("is_healthy method must be implemented by subclasses")


class InMemoryDatabase(BaseDatabase):
    def __init__(self, checkpointer: InMemorySaver):
        super().__init__(checkpointer)

    async def is_healthy(self) -> bool:
        return True


class RedisDatabase(BaseDatabase):
    def __init__(self, redis_client: Redis, checkpointer: AsyncRedisSaver):
        super().__init__(checkpointer)
        self.redis_client = redis_client

    async def is_healthy(self) -> bool:
        try:
            pong = self.redis_client.ping()
            return pong is True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


class PostgresDatabase(BaseDatabase):
    def __init__(self, conn: AsyncConnection, checkpointer: AsyncPostgresSaver):
        super().__init__(checkpointer)
        self.conn = conn

    async def is_healthy(self) -> bool:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            result = await cursor.fetchone()
            return result is not None and result[0] == 1


from contextlib import asynccontextmanager
from typing import AsyncIterator

@asynccontextmanager
async def create_database() -> AsyncIterator[BaseDatabase]:
    # Use Redis if enabled
    if REDIS_ENABLED:
        redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        checkpointer = AsyncRedisSaver(redis_client=redis_client)
        await checkpointer.asetup()
        yield RedisDatabase(redis_client=redis_client, checkpointer=checkpointer)
    # Use Postgres if enabled
    elif POSTGRES_ENABLED:
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
            #"row_factory": dict_row,
        }
        async with AsyncConnectionPool(DB_URI,kwargs=connection_kwargs) as pool:
            async with pool.connection(timeout=5) as conn:
                checkpointer = AsyncPostgresSaver(conn=conn)
                await checkpointer.setup()
                yield PostgresDatabase(conn=conn,checkpointer=checkpointer)
    # Default to in-memory database
    else:
        yield InMemoryDatabase(checkpointer=InMemorySaver())


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
