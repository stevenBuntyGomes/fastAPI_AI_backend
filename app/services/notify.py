# app/services/notify.py
import asyncio
from typing import Any
from app.services.socket_manager import emit_to_user

def emit_to_user_bg(user_id: str, event: str, payload: Any) -> None:
    """
    Fire-and-forget emit so your route returns fast.
    Safe to call from controllers after DB writes succeed.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(emit_to_user(user_id, event, payload))
    except RuntimeError:
        # No running loop (rare in FastAPI routes). Fallback to direct await via new loop.
        asyncio.run(emit_to_user(user_id, event, payload))
