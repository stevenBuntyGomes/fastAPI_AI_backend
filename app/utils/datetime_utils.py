# app/utils/datetime_utils.py
from datetime import datetime, timezone

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_utc_aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
