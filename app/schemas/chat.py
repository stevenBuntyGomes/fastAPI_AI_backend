from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str  # Only message is needed from the frontend

class ChatResponse(BaseModel):
    response: str
