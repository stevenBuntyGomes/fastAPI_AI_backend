# app/utils/moderation.py
from __future__ import annotations
import re, unicodedata
from typing import Dict
from unidecode import unidecode
from better_profanity import profanity

profanity.load_censor_words()

LEET = str.maketrans({"0":"o","1":"i","!":"i","3":"e","4":"a","@":"a","5":"s","7":"t","$":"s","8":"b"})

def _normalize(text: str) -> str:
    t = unidecode(unicodedata.normalize("NFKD", (text or "").lower()))
    t = t.translate(LEET)
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)        # cooool -> cool
    t = re.sub(r"[^a-z0-9\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()

def moderate_text(text: str, lang: str = "en") -> Dict:
    normalized = _normalize(text)
    flagged = profanity.contains_profanity(normalized)
    cleaned = profanity.censor(text or "", censor_char="*")
    return {"cleaned": cleaned, "flagged": flagged, "reason": "profanity" if flagged else "clean"}
