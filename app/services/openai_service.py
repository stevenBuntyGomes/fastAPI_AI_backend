import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, AsyncGenerator

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_chatgpt_stream(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    try:
        # Start the GPT-4o stream
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            stream=True  # Enable streaming
        )

        # Yield content chunks one at a time
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except Exception as e:
        yield f"[ERROR] {str(e)}"