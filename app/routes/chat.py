from fastapi import APIRouter
from ..schemas.chat import ChatRequest, ChatResponse
from ..db.mongo import memory_collection
from ..models.memory import format_memory
from ..services.openai_service import ask_chatgpt

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat_with_gpt(request: ChatRequest):
    # 1. Get user's previous memory
    memory_cursor = memory_collection.find({"user_id": request.user_id}).sort("_id", -1).limit(5)
    previous_messages = await memory_cursor.to_list(length=5)

    # 2. Prepare messages for GPT
    context_messages = []
    for item in reversed(previous_messages):  # oldest to newest
        context_messages.append({"role": "user", "content": item["message"]})
        context_messages.append({"role": "assistant", "content": item["response"]})

    # Add current message
    context_messages.append({"role": "user", "content": request.message})

    # 3. Ask GPT
    gpt_reply = await ask_chatgpt(context_messages)

    # 4. Save new memory
    new_memory = format_memory(request.user_id, request.message, gpt_reply)
    await memory_collection.insert_one(new_memory)

    # 5. Return response
    return {"response": gpt_reply}
