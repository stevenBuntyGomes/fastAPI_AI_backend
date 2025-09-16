# app/services/openai_service.py
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from typing import AsyncGenerator, Optional
from datetime import datetime
from bson import ObjectId

# ✅ collections
from ..db.mongo import memory_collection, users_collection

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")


# ---- helper: fetch user's name only ----
async def _fetch_user_name(user_id: str) -> Optional[str]:
    try:
        uid = ObjectId(user_id)
    except Exception:
        return None
    doc = await users_collection.find_one({"_id": uid}, {"name": 1})
    return (doc or {}).get("name")


def _build_run_instructions(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return (
        f"The user's name is {name}. Address them by their name naturally when appropriate. "
        "Be supportive, concise, and practical. Avoid medical claims; suggest evidence-based "
        "tips and encourage healthy habits."
    )


# ---------------- GPT Streaming + Save Memory (original logic kept) ----------------
async def ask_chatgpt_stream_assistant(user_id: str, user_input: str) -> AsyncGenerator[str, None]:
    full_response = ""

    try:
        # Optional personalization
        name = await _fetch_user_name(user_id)
        run_instructions = _build_run_instructions(name)

        # Step 1: Create thread
        thread = await client.beta.threads.create()

        # Step 2: Add user message
        await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Step 3: Start run with streaming (+ optional instructions)
        run_kwargs = {"stream": True}
        if run_instructions:
            run_kwargs["instructions"] = run_instructions

        stream = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            **run_kwargs
        )

        # Step 4: Yield streamed chunks and collect full response
        async for event in stream:
            if event.event == "thread.message.delta":
                delta = event.data.delta
                if hasattr(delta, "content") and delta.content:
                    for item in delta.content:
                        if getattr(item, "type", None) == "text":
                            text = item.text.value
                            full_response += text
                            yield text

        # Step 5: Save memory in DB after stream ends
        await memory_collection.insert_one({
            "user_id": ObjectId(user_id),
            "message": user_input,
            "response": full_response,
            "timestamp": datetime.utcnow()
        })

    except Exception as e:
        print("❌ GPT Stream Error:", e)
        # Keep outward behavior stable
        yield "[ERROR] GPT returned an empty response."
