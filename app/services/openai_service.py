import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_chatgpt(message: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # 👈 Using gpt-4o
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "You are a helpful assistant."}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message}
                    ]
                }
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error from GPT: {str(e)}"
