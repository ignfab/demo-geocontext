import logging
logger = logging.getLogger(__name__)

import os

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.memory import InMemorySaver

from redis.asyncio import Redis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncConnection
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DB_URI = os.getenv("DB_URI",None)

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
            pong = await self.redis_client.ping()
            return pong is True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


class PostgresDatabase(BaseDatabase):
    def __init__(self, conn: AsyncConnection, checkpointer: AsyncPostgresSaver):
        super().__init__(checkpointer)
        self.conn = conn

    async def is_healthy(self) -> bool:
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                return result is not None and result[0] == 1
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

@asynccontextmanager
async def create_database() -> AsyncIterator[BaseDatabase]:
    if DB_URI is None or DB_URI == "":
        logger.info("create InMemoryDatabase as DB_URI is not defined")
        yield InMemoryDatabase(checkpointer=InMemorySaver())
    # Use Redis ?
    elif DB_URI.startswith("redis://"):
        logger.debug("create Redis client...")
        redis_client = Redis.from_url(DB_URI)
        logger.debug("create AsyncRedisSaver checkpointer...")
        checkpointer = AsyncRedisSaver(redis_client=redis_client)
        logger.debug("setup AsyncRedisSaver checkpointer...")
        await checkpointer.asetup()
        logger.info("RedisDatabase created")
        yield RedisDatabase(redis_client=redis_client, checkpointer=checkpointer)
    # Use PostgresSQL?
    elif DB_URI.startswith("postgresql://"):
        logger.info("create AsyncConnectionPool for PostgreSQL...")
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
            #"row_factory": dict_row,
        }
        async with AsyncConnectionPool(DB_URI,kwargs=connection_kwargs) as pool:
            logger.debug("create connection...")
            async with pool.connection(timeout=5) as conn:
                logger.debug("create AsyncPostgresSaver...")
                checkpointer = AsyncPostgresSaver(conn=conn)
                logger.debug("setup AsyncPostgresSaver...")
                await checkpointer.setup()
                logger.debug("PostgresDatabase created")
                yield PostgresDatabase(conn=conn,checkpointer=checkpointer)
    # Default to in-memory database
    else:
        error_message = f"Invalid DB_URI (not starting with redis:// or postgresql://)"
        raise RuntimeError(error_message)


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
