import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_chatgpt(messages: List[Dict[str, str]]) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # or gpt-4 / gpt-3.5-turbo
            messages=messages,  # 👈 Now this is your full message history
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error from GPT: {str(e)}"
