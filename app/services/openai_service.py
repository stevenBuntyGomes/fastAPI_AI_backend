import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_chatgpt(message: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are a helpful assistant."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": message  # ✅ Must be a string
                        }
                    ]
                }
            ],
            temperature=0.7
        )

        # ✅ Make sure response content exists
        content = response.choices[0].message.content
        if isinstance(content, list) and len(content) > 0 and "text" in content[0]:
            return content[0]["text"].strip()
        else:
            return "⚠️ GPT responded, but no text content found."

    except Exception as e:
        return f"Error from GPT: {str(e)}"
