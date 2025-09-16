# app/services/openai_service.py
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from typing import AsyncGenerator, Optional, Dict, List
from datetime import datetime
from bson import ObjectId

# ✅ import your collections so we can fetch user + onboarding context
from ..db.mongo import memory_collection, users_collection, onboarding_collection

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

# -------- helpers to build personalization context --------

async def _fetch_user_and_onboarding(user_id: str) -> Dict:
    """
    Returns {
      'name': Optional[str],
      'email': Optional[str],
      'onboarding': Optional[dict]
    }
    """
    out: Dict = {"name": None, "email": None, "onboarding": None}
    try:
        uid = ObjectId(user_id)
    except Exception:
        return out

    user = await users_collection.find_one(
        {"_id": uid},
        {"name": 1, "email": 1, "onboarding_id": 1}
    )
    if not user:
        return out

    out["name"] = user.get("name")
    out["email"] = user.get("email")

    ob_id = user.get("onboarding_id")
    if ob_id:
        ob = await onboarding_collection.find_one({"_id": ob_id})
        if ob:
            out["onboarding"] = ob

    return out


def _summarize_onboarding(ob: dict) -> str:
    """
    Turn an onboarding document into a compact, safe summary the model can use.
    Only includes fields that exist. Keeps it short & actionable.
    """
    if not ob:
        return ""

    lines: List[str] = []

    def add(label: str, key: str):
        v = ob.get(key)
        if v is not None and v != "":
            lines.append(f"{label}: {v}")

    # Smoking/vaping profile
    add("Vaping frequency", "vaping_frequency")
    add("Triggers", "vaping_trigger")
    add("Effects", "vaping_effect")
    add("Hides vaping", "hides_vaping")

    # Numbers & costs
    add("Years vaping", "vaping_years")
    add("Device lifespan (days)", "vape_lifespan_days")
    add("Puffs per device", "puff_count")
    add("Monthly cost (USD)", "vape_cost_usd")

    # Attempts & source
    add("Quit attempts", "quit_attempts")
    add("Referral source", "referral_source")

    # Profile
    add("First name", "first_name")
    add("Gender", "gender")
    add("Age", "age")

    if not lines:
        return ""

    return "- " + "\n- ".join(lines)


def _build_run_instructions(name: Optional[str], onboarding: Optional[dict]) -> Optional[str]:
    """
    Build the per-run instruction string. If nothing to add, returns None.
    """
    parts: List[str] = []

    if name:
        parts.append(
            f"The user's name is {name}. Address them by their name naturally when appropriate."
        )

    summary = _summarize_onboarding(onboarding) if onboarding else ""
    if summary:
        parts.append(
            "User onboarding profile (use to personalize quit-vaping support; do not reveal private details unless asked):\n"
            f"{summary}"
        )

    if not parts:
        return None

    # Gentle guardrails
    parts.append(
        "Be supportive, concise, and practical. Avoid medical claims; suggest evidence-based tips and encourage healthy habits."
    )

    return "\n\n".join(parts)

# ------------------ NO BREAKING CHANGES BELOW ------------------

# GPT Streaming + Save Memory
async def ask_chatgpt_stream_assistant(user_id: str, user_input: str) -> AsyncGenerator[str, None]:
    """
    Streams assistant output. Now includes per-user personalization
    via run-level `instructions` (user name + onboarding).
    """
    full_response = ""

    try:
        # Build personalization context (non-blocking if missing)
        ctx = await _fetch_user_and_onboarding(user_id)
        run_instructions = _build_run_instructions(ctx.get("name"), ctx.get("onboarding"))

        # Step 1: Create thread
        thread = await client.beta.threads.create()

        # Step 2: Add user message (unchanged)
        await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Step 3: Start run with streaming + optional instructions
        run_kwargs = {"stream": True}
        if run_instructions:
            run_kwargs["instructions"] = run_instructions

        stream = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            **run_kwargs
        )

        # Step 4: Yield streamed chunks and collect full response (unchanged)
        async for event in stream:
            if event.event == "thread.message.delta":
                delta = event.data.delta
                if hasattr(delta, "content") and delta.content:
                    for item in delta.content:
                        if getattr(item, "type", None) == "text":
                            text = item.text.value
                            full_response += text
                            yield text

        # Step 5: Save memory in DB after stream ends (unchanged)
        await memory_collection.insert_one({
            "user_id": ObjectId(user_id),   # ✅ ObjectId linkage
            "message": user_input,
            "response": full_response,
            "timestamp": datetime.utcnow()
        })

    except Exception as e:
        print("❌ GPT Stream Error:", e)
        # Keep your wire protocol stable: still emit a plain text line
        yield "[ERROR] GPT returned an empty response."
