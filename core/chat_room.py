from pydantic import BaseModel
from datetime import datetime
import json
import os
import redis

# Initialize Redis client with environment variables or default values
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0
)

class ChatMessage(BaseModel):
    timestamp: str = datetime.now().isoformat()
    role: str
    content: str

class ChatRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.messages = []
        # Try to load from Redis sorted set, but handle connection errors gracefully
        try:
            raw_msgs = r.lrange(f"room:{self.room_id}:messages", 0, -1)
            self.messages = [ChatMessage.parse_raw(m) for m in raw_msgs]
        except Exception as e:
            print(f"Redis connection error, using in-memory storage: {e}")
            self.messages = []

    def get_messages(self) -> list[ChatMessage]:
        return self.messages

    def add_message(self, content: str):
        message = ChatMessage(role="User", content=content)
        self.messages.append(message)
        # Try to save to Redis, but don't fail if Redis is not available
        try:
            r.lpush(f"room:{self.room_id}:messages", message.model_dump_json())
        except Exception as e:
            print(f"Redis save error, keeping in memory only: {e}")
        return message

def get_chat_room(name: str) -> ChatRoom:
    return ChatRoom(name)
