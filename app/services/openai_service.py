from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from typing import AsyncGenerator

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

# FIXED Streaming Assistant Function
async def ask_chatgpt_stream_assistant(user_id: str, user_input: str) -> AsyncGenerator[str, None]:
    try:
        # Step 1: Create thread
        thread = await client.beta.threads.create()

        # Step 2: Add user message
        await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Step 3: Start run with streaming
        stream = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            stream=True
        )

        # Step 4: Yield streamed chunks correctly
        async for event in stream:
            if event.event == "thread.message.delta":
                delta = event.data.delta
                if hasattr(delta, "content") and delta.content:
                    for item in delta.content:
                        if item.type == "text":
                            yield item.text.value

    except Exception as e:
        print("❌ GPT Stream Error:", e)
        yield "[ERROR] GPT returned an empty response."
