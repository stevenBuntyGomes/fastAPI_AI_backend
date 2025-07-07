import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, AsyncGenerator
# service is causing problem in live server
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Non-streaming version (still usable elsewhere)
async def ask_chatgpt(messages: List[Dict[str, str]]) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,  # ✅ Lowered temperature for speed
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error from GPT: {str(e)}"

# Streaming version
async def ask_chatgpt_stream(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    try:
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,  # ✅ Lowered temperature for faster and more deterministic replies
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except Exception as e:
        yield f"[ERROR] {str(e)}"
