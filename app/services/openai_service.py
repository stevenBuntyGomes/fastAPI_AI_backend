import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_chatgpt(message: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # this works for gpt-4o and gpt-4 if content is string
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error from GPT: {str(e)}"
