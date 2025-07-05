from typing import List, Dict

def format_memory(user_id: str, message: str, response: str) -> Dict:
    return {
        "user_id": user_id,
        "message": message,
        "response": response
    }
