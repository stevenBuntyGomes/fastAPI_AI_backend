from datetime import datetime
from typing import Any
from pydantic import BaseModel, model_serializer

_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%f"  # e.g. 2025-09-19T19:17:43.904000

def _to_naive_iso(v: Any):
    if isinstance(v, datetime):
        # strip tzinfo and format with 6-digit microseconds (no 'Z', no offset)
        return v.replace(tzinfo=None).strftime(_DATETIME_FMT)
    if isinstance(v, list):
        return [_to_naive_iso(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_naive_iso(val) for k, val in v.items()}
    return v

class NaiveIsoDatetimeModel(BaseModel):
    """Serialize ALL datetime fields (including nested lists/dicts) as YYYY-MM-DDTHH:mm:ss.SSSSSS."""
    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        return _to_naive_iso(data)