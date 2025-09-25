# app/routes/devices.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, OperationFailure
import os, re, asyncio

from app.db.mongo import devices_collection

router = APIRouter(prefix="/devices", tags=["devices"])

HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterDeviceBody(BaseModel):
    user_id: str = Field(..., description="Mongo ObjectId of the user")
    token: str = Field(..., description="APNs device token (hex)")
    bundle_id: Optional[str] = Field(None, description="App bundle id (topic). Optional to store.")
    environment: Optional[Literal["sandbox", "production"]] = Field(
        None, description="If omitted, server infers (localhost/LAN => sandbox, else production)"
    )

# --------------------------
# One-time self-heal (run from this module, not main.py)
# --------------------------
_bootstrap_done = False
_bootstrap_lock = asyncio.Lock()

async def _bootstrap_devices_collection_once():
    global _bootstrap_done
    if _bootstrap_done:
        return
    async with _bootstrap_lock:
        if _bootstrap_done:
            return
        # 1) normalize old env casing
        try:
            await devices_collection.update_many(
                {"environment": "Production"}, {"$set": {"environment": "production"}}
            )
            await devices_collection.update_many(
                {"environment": "Sandbox"}, {"$set": {"environment": "sandbox"}}
            )
        except Exception as e:
            print(f"[devices.bootstrap] normalize env casing skipped: {e}")

        # 2) drop legacy unique index on {user_id, platform} if present
        try:
            info = await devices_collection.index_information()
            for name, spec in info.items():
                key = spec.get("key", [])
                # key e.g. [('user_id', 1), ('platform', 1)]
                if (
                    isinstance(key, list) and len(key) == 2
                    and key[0][0] == "user_id" and key[1][0] == "platform"
                    and spec.get("unique")
                ):
                    try:
                        await devices_collection.drop_index(name)
                        print(f"[devices.bootstrap] dropped legacy index: {name}")
                    except Exception as e:
                        print(f"[devices.bootstrap] drop index {name} failed: {e}")
        except Exception as e:
            print(f"[devices.bootstrap] inspect indexes failed: {e}")

        # 3) ensure correct unique index per environment
        try:
            await devices_collection.create_index(
                [("user_id", 1), ("platform", 1), ("environment", 1)],
                unique=True, name="uniq_user_platform_env"
            )
        except Exception as e:
            print(f"[devices.bootstrap] ensure uniq_user_platform_env failed: {e}")

        # Optional: unique token index (commented out to avoid cross-user conflicts)
        # try:
        #     await devices_collection.create_index([("token", 1)], unique=True, name="uniq_token")
        # except Exception as e:
        #     print(f"[devices.bootstrap] ensure uniq_token failed: {e}")

        _bootstrap_done = True

# --------------------------
# Helpers
# --------------------------
def _infer_env_from_request(req: Request) -> str:
    # Heuristic: localhost/LAN → sandbox; anything public → production
    host = (req.headers.get("x-forwarded-host") or req.headers.get("host") or "").lower()
    if (
        "localhost" in host
        or host.startswith(("127.0.0.1", "10.", "192.168.", "172.16.", "172.17.", "172.18.",
                            "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                            "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                            "172.29.", "172.30.", "172.31."))
    ):
        return "sandbox"
    return "production"

# --------------------------
# Route
# --------------------------
@router.post("/apns")
async def register_apns_device(body: RegisterDeviceBody, request: Request):
    # Ensure collection is healthy (indexes, old values) without touching main.py
    await _bootstrap_devices_collection_once()

    # 1) validate inputs
    try:
        user_oid = ObjectId(body.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # Keep sanitizer: prevents storing junk (angle brackets/spaces/base64)
    token = re.sub(r"[^0-9a-fA-F]", "", body.token or "")
    if not HEX_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    # 2) decide environment (store LOWERCASE to satisfy validators/indexes)
    if body.environment:
        env_norm = body.environment.strip().lower()
        if env_norm not in ("production", "sandbox"):
            raise HTTPException(status_code=422, detail="environment must be 'sandbox' or 'production'")
    else:
        env_norm = _infer_env_from_request(request)

    # Accept missing bundle_id at store time (you’ll need it when sending)
    bundle_id = body.bundle_id or os.getenv("APNS_BUNDLE_ID")

    # Prepare doc (store lowercase)
    doc = {
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": bundle_id,
        "environment": env_norm,   # 'production' or 'sandbox' (lowercase)
        "updated_at": datetime.utcnow(),
    }

    # Match either lowercase or legacy capitalized env to update in place
    env_variants = [env_norm, env_norm.capitalize()]  # e.g., 'production','Production'

    # 3) upsert with robust fallbacks so it ALWAYS stores
    try:
        result = await devices_collection.update_one(
            {"user_id": user_oid, "platform": "ios", "environment": {"$in": env_variants}},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
    except DuplicateKeyError:
        # If a legacy unique index exists on {user_id, platform}, update that row
        try:
            result = await devices_collection.update_one(
                {"user_id": user_oid, "platform": "ios"},
                {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
                upsert=True,
            )
        except DuplicateKeyError:
            # If there’s a unique token index collision, update by token
            result = await devices_collection.update_one(
                {"token": token},
                {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
                upsert=True,
            )
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"DB duplicate error: {str(e2)}")
    except OperationFailure as e:
        # Expose validator errors (e.g., env enum mismatch)
        raise HTTPException(
            status_code=422,
            detail=f"DB validation failed: {e.details if hasattr(e, 'details') else str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")

    return {
        "ok": True,
        "environment": env_norm,  # lowercase
        "matched": result.matched_count,
        "upserted_id": str(result.upserted_id) if result.upserted_id else None,
    }
