# openai_service.py
import os
import asyncio
from typing import AsyncGenerator
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

async def ask_chatgpt_stream_assistant(user_id: str, user_input: str) -> AsyncGenerator[str, None]:
    try:
        # Step 1: Create new thread
        thread = client.beta.threads.create()

        # Step 2: Add user message
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Step 3: Start run
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Step 4: Poll for completion
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status in ["completed", "failed", "cancelled", "expired"]:
                break
            await asyncio.sleep(0.5)

        # Step 5: Retrieve messages
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_messages = [m for m in reversed(messages.data) if m.role == "assistant"]

        if not assistant_messages or not assistant_messages[0].content:
            yield "[ERROR] GPT returned an empty response."
        else:
            for block in assistant_messages[0].content:
                if block.type == "text":
                    yield block.text.value

    except Exception as e:
        print("❌ GPT Error:", e)
        yield f"[ERROR] {str(e)}"
