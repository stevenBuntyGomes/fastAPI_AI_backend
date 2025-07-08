from fastapi import APIRouter, HTTPException
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.openai_service import ask_chatgpt_assistant

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        if not request.user_id or not request.message:
            raise HTTPException(status_code=400, detail="Missing user_id or message")

        reply = ask_chatgpt_assistant(request.user_id, request.message)
        return {"response": reply}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
