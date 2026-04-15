"""Checkpointers LangGraph (mémoire, Redis, Postgres), create_database, database_lifecycle, get_database."""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis

from ..config import DB_URI

logger = logging.getLogger(__name__)


class BaseDatabase:
    def __init__(self, checkpointer: InMemorySaver | AsyncRedisSaver | AsyncPostgresSaver):
        self.checkpointer = checkpointer

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
            logger.error("Redis health check failed: %s", e)
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
            logger.error("PostgreSQL health check failed: %s", e)
            return False


@asynccontextmanager
async def get_database() -> AsyncIterator[BaseDatabase]:
    if DB_URI is None or DB_URI == "":
        logger.info("create InMemoryDatabase as DB_URI is not defined")
        yield InMemoryDatabase(checkpointer=InMemorySaver())
    elif DB_URI.startswith("redis://"):
        logger.debug("create Redis client...")
        redis_client = Redis.from_url(DB_URI)
        logger.debug("create AsyncRedisSaver checkpointer...")
        checkpointer = AsyncRedisSaver(redis_client=redis_client)
        logger.debug("setup AsyncRedisSaver checkpointer...")
        await checkpointer.asetup()
        logger.info("RedisDatabase created")
        yield RedisDatabase(redis_client=redis_client, checkpointer=checkpointer)
    elif DB_URI.startswith("postgresql://"):
        logger.info("create AsyncConnectionPool for PostgreSQL...")
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        async with AsyncConnectionPool(DB_URI, kwargs=connection_kwargs) as pool:
            logger.debug("create connection...")
            async with pool.connection(timeout=5) as conn:
                logger.debug("create AsyncPostgresSaver...")
                checkpointer = AsyncPostgresSaver(conn=conn)
                logger.debug("setup AsyncPostgresSaver...")
                await checkpointer.setup()
                logger.debug("PostgresDatabase created")
                yield PostgresDatabase(conn=conn, checkpointer=checkpointer)
    else:
        raise RuntimeError("Invalid DB_URI (not starting with redis:// or postgresql://)")


async def get_thread_ids(checkpointer: AsyncRedisSaver) -> list[str]:
    """Find thread_ids by inspecting checkpointer"""
    thread_ids = []

    try:
        logger.info("get_thread_ids(checkpointer) ...")
        async for checkpoint_tuple in checkpointer.alist({}):
            config = checkpoint_tuple.config
            if "configurable" in config and "thread_id" in config["configurable"]:
                thread_id = config["configurable"]["thread_id"]
                if thread_id and thread_id not in thread_ids:
                    thread_ids.append(thread_id)
    except Exception as e:
        logger.warning("Fail to retrieve thread ids from checkpointer: %s", e)

    logger.debug("get_thread_ids(checkpointer) - sort and return thread_ids...")
    thread_ids.sort()
    return thread_ids
