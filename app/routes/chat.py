from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..schemas.chat import ChatRequest
from ..services.openai_service import ask_chatgpt_stream_assistant
from ..utils.auth_utils import get_current_user

router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)  # ✅ Secure route
):
    try:
        user_id = str(current_user["_id"])  # Use authenticated user's ObjectId
        if not request.message:
            raise HTTPException(status_code=400, detail="Missing message")

        async def gpt_event_stream():
            async for chunk in ask_chatgpt_stream_assistant(user_id, request.message):
                if chunk:
                    yield chunk

        return StreamingResponse(gpt_event_stream(), media_type="text/plain")

    except Exception as e:
        print("❌ Chat Stream Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
