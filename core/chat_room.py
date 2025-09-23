from pydantic import BaseModel
from datetime import datetime
import json
import os
import redis.asyncio as redis

# Initialize Redis client with environment variables or default values
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0
)

# Dictionnaire global pour partager les instances de ChatRoom
chat_rooms: dict[str, "ChatRoom"] = {}

class ChatMessage(BaseModel):
    timestamp: str = datetime.now().isoformat()
    role: str
    content: str

class ChatRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.messages = []

    async def load_messages(self):
        """Charge les messages depuis Redis de manière asynchrone"""
        try:
            raw_msgs = await r.lrange(f"room:{self.room_id}:messages", 0, -1)
            self.messages = [ChatMessage.parse_raw(m) for m in raw_msgs]
        except Exception as e:
            print(f"Redis connection error, using in-memory storage: {e}")
            self.messages = []

    async def get_messages(self) -> list[ChatMessage]:
        """Récupère les messages de manière asynchrone"""
        # Si les messages ne sont pas encore chargés, les charger depuis Redis
        if not self.messages:
            await self.load_messages()
        return self.messages

    async def add_message(self, content: str) -> ChatMessage:
        """Ajoute un message de manière asynchrone"""
        message = ChatMessage(role="User", content=content)
        self.messages.append(message)
        # Try to save to Redis, but don't fail if Redis is not available
        try:
            await r.lpush(f"room:{self.room_id}:messages", message.model_dump_json())
        except Exception as e:
            print(f"Redis save error, keeping in memory only: {e}")
        return message

async def get_chat_room(name: str) -> ChatRoom:
    """Récupère ou crée une chat room partagée de manière asynchrone"""
    # Vérifie si la chat room existe déjà dans le dictionnaire global
    if name not in chat_rooms:
        # Crée une nouvelle instance et la stocke dans le dictionnaire global
        chat_rooms[name] = ChatRoom(name)
        await chat_rooms[name].load_messages()
    
    return chat_rooms[name]
