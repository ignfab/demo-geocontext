
from fastapi import FastAPI
from pydantic import BaseModel

from core.chat_room import get_chat_room, ChatMessage

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

class MessageRequest(BaseModel):
    content: str

@app.get("/chat/{room_name}/messages")
async def get_messages(room_name: str) -> list[ChatMessage]:
    chat_room = get_chat_room(room_name)
    return chat_room.get_messages()

@app.post("/chat/{room_name}/messages")
async def add_message(room_name: str, message: MessageRequest) -> ChatMessage :
    chat_room = get_chat_room(room_name)
    return chat_room.add_message(message.content)

# @app.get("/")
# async def root():
#     return {"message": "Hello World"}
