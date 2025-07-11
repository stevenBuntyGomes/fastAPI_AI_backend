from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..schemas.chat import ChatRequest
from ..services.openai_service import ask_chatgpt_stream_assistant

router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    try:
        if not request.user_id or not request.message:
            raise HTTPException(status_code=400, detail="Missing user_id or message")

        async def gpt_event_stream():
            async for chunk in ask_chatgpt_stream_assistant(request.user_id, request.message):
                if chunk:
                    yield chunk

        return StreamingResponse(gpt_event_stream(), media_type="text/plain")

    except Exception as e:
        print("❌ Chat Stream Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
