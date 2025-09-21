# app/services/oauth_utils.py
import os
import time
import logging
from functools import lru_cache
from typing import Optional, Dict, Any

import jwt  # PyJWT
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# =========
# ENV VARS
# =========
# Google:
GOOGLE_WEB_CLIENT_ID = os.getenv("GOOGLE_WEB_CLIENT_ID")         # web app client_id (if you have one)
GOOGLE_IOS_CLIENT_ID = os.getenv("GOOGLE_IOS_CLIENT_ID")         # iOS client_id (from GoogleService-Info.plist)

# Apple:
APPLE_BUNDLE_ID   = os.getenv("APPLE_BUNDLE_ID")                 # e.g., com.breathr.breathrapp (iOS native)
APPLE_SERVICES_ID = os.getenv("APPLE_SERVICES_ID")               # e.g., com.breathr.web (if you add Apple login on web)

# Build allowed audiences (keep identical behavior to your previous code)
_ALLOWED_GOOGLE_AUDS = {cid for cid in [GOOGLE_WEB_CLIENT_ID, GOOGLE_IOS_CLIENT_ID] if cid}
_ALLOWED_APPLE_AUDS  = [v for v in [APPLE_BUNDLE_ID, APPLE_SERVICES_ID] if v]

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


# =========
# GOOGLE
# =========
def verify_google_token(token_id: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a Google ID token and returns {'email', 'name', 'sub'} on success, else None.
    Signature matches your existing function; frontend does NOT need to change.
    """
    try:
        if not _ALLOWED_GOOGLE_AUDS:
            logging.error("Google verification blocked: no GOOGLE_*_CLIENT_ID env vars configured.")
            return None

        # Verify signature & expiry against Google's public keys.
        # We pass audience=None here and enforce allowed audiences ourselves (back-compat with your env-based list).
        req = google_requests.Request()
        payload = google_id_token.verify_oauth2_token(token_id, req, audience=None)

        # Harden claims (mirror your previous checks)
        iss_ok = payload.get("iss") in {"accounts.google.com", "https://accounts.google.com"}
        aud_ok = payload.get("aud") in _ALLOWED_GOOGLE_AUDS
        email = payload.get("email")
        email_verified_raw = payload.get("email_verified")
        email_verified = (email_verified_raw in (True, "true", "1", 1))

        # google_id_token.verify_oauth2_token already checks 'exp', but we keep your explicit behavior
        exp = int(payload.get("exp", "0"))
        not_expired = exp > int(time.time())

        if not (iss_ok and aud_ok and email and email_verified and not_expired):
            logging.warning(
                "Google token rejected. iss_ok=%s, aud_ok=%s, email=%s, email_verified=%s, not_expired=%s",
                iss_ok, aud_ok, bool(email), email_verified, not_expired
            )
            return None

        name = payload.get("name") or payload.get("given_name") or "Google User"
        return {"email": email, "name": name, "sub": payload.get("sub")}
    except Exception:
        logging.exception("Google token verification failed with exception")
        return None


# =========
# APPLE
# =========

@lru_cache(maxsize=1)
def _apple_jwk_client() -> PyJWKClient:
    # PyJWKClient handles fetching & caching Apple's keys (no RSAAlgorithm import needed)
    return PyJWKClient(APPLE_JWKS_URL)

def _decode_apple_with_any_allowed_aud(identity_token: str, signing_key) -> Optional[Dict[str, Any]]:
    """
    Some PyJWT versions prefer a single audience string; to stay bulletproof,
    try each allowed audience until one succeeds (keeps your env-driven behavior).
    """
    if not _ALLOWED_APPLE_AUDS:
        return None

    last_error: Optional[Exception] = None
    for aud in _ALLOWED_APPLE_AUDS:
        try:
            claims = jwt.decode(
                identity_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=aud,
                issuer=APPLE_ISSUER,
                options={"require": ["iss", "aud", "exp", "iat"]},
            )
            return claims
        except Exception as e:
            last_error = e
            continue
    if last_error:
        logging.warning("Apple token failed audience check against allowed audiences: %s", _ALLOWED_APPLE_AUDS)
    return None

def verify_apple_token(identity_token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies an Apple Sign-In identity token (JWT).
    Returns {'email'?, 'name', 'sub'} on success (email may be absent after first sign-in), else None.
    Signature matches your existing function; frontend does NOT need to change.
    """
    try:
        if not _ALLOWED_APPLE_AUDS:
            logging.error("Apple verification blocked: no APPLE_BUNDLE_ID / APPLE_SERVICES_ID configured.")
            return None

        # Resolve signing key via Apple's JWKS
        jwk_client = _apple_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(identity_token)

        # Decode + validate with allowed audiences & issuer
        claims = _decode_apple_with_any_allowed_aud(identity_token, signing_key)
        if not claims:
            return None

        # Optional: email & email_verified checks (same semantics as your previous code)
        email = claims.get("email")
        email_verified_raw = claims.get("email_verified")
        email_verified = (
            True if email_verified_raw is None else
            (email_verified_raw in (True, "true", "1", 1))
        )
        if email is not None and not email_verified:
            logging.warning("Apple token has email but not verified.")
            return None

        name = claims.get("name") or "Apple User"
        return {"email": email, "name": name, "sub": claims.get("sub")}

    except ExpiredSignatureError:
        logging.warning("Apple token expired")
        return None
    except InvalidTokenError as e:
        logging.warning("Apple token invalid: %s", str(e))
        return None
    except Exception:
        logging.exception("Apple token verification failed with exception")
        return None
