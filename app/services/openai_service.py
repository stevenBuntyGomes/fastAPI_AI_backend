from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

def ask_chatgpt_assistant(user_id: str, user_input: str) -> str:
    try:
        # Step 1: Create a thread
        thread = client.beta.threads.create()

        # Step 2: Add user message
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Step 3: Start assistant run
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Step 4: Poll until complete
        while True:
            status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if status.status in ["completed", "failed", "cancelled", "expired"]:
                break

        # Step 5: Get final assistant message
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_messages = [m for m in reversed(messages.data) if m.role == "assistant"]

        if not assistant_messages or not assistant_messages[0].content:
            return "[ERROR] GPT returned an empty response."

        for block in assistant_messages[0].content:
            if block.type == "text":
                return block.text.value

        return "[ERROR] No text found in assistant response."

    except Exception as e:
        print("❌ Assistant error:", e)
        return f"[ERROR] {str(e)}"
