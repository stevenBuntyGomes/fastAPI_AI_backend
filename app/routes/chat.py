from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..schemas.chat import ChatRequest
from ..db.mongo import memory_collection
from ..models.memory import format_memory
from ..services.openai_service import ask_chatgpt_stream

router = APIRouter()

@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    user_id = request.user_id
    message = request.message

    # 1. Get last 5 messages from memory
    memory_cursor = memory_collection.find({"user_id": user_id}).sort("_id", -1).limit(5)
    previous_messages = await memory_cursor.to_list(length=5)

    # 2. Prepare GPT context
    context_messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for item in reversed(previous_messages):
        context_messages.append({"role": "user", "content": item["message"]})
        context_messages.append({"role": "assistant", "content": item["response"]})
    context_messages.append({"role": "user", "content": message})

    # 3. Streaming generator
    async def gpt_event_stream():
        full_response = ""
        async for chunk in ask_chatgpt_stream(context_messages):
            full_response += chunk
            yield chunk
        # 4. Save full memory after streaming
        await memory_collection.insert_one(format_memory(user_id, message, full_response))

    # 5. Return streaming response
    return StreamingResponse(gpt_event_stream(), media_type="text/plain")
