# app/services/oauth_utils.py
import os
import time
import json
import logging
from typing import Optional, Dict

import requests
import jwt
from jwt.algorithms import RSAAlgorithm

# =========
# ENV VARS
# =========
# Google:
GOOGLE_WEB_CLIENT_ID = os.getenv("GOOGLE_WEB_CLIENT_ID")         # web app client_id (if you have one)
GOOGLE_IOS_CLIENT_ID = os.getenv("GOOGLE_IOS_CLIENT_ID")         # iOS client_id (from GoogleService-Info.plist)

# Apple:
APPLE_BUNDLE_ID     = os.getenv("APPLE_BUNDLE_ID")               # e.g., com.breathr.breathrapp (iOS native)
APPLE_SERVICES_ID   = os.getenv("APPLE_SERVICES_ID")             # e.g., com.breathr.web (if you add Apple login on web)

# Build allowed audiences
_ALLOWED_GOOGLE_AUDS = {cid for cid in [GOOGLE_WEB_CLIENT_ID, GOOGLE_IOS_CLIENT_ID] if cid}
_ALLOWED_APPLE_AUDS  = [v for v in [APPLE_BUNDLE_ID, APPLE_SERVICES_ID] if v]

# =========
# GOOGLE
# =========
def verify_google_token(token_id: str) -> Optional[Dict]:
    """
    Verifies a Google ID token by hitting Google's tokeninfo endpoint and checking claims.
    Returns dict with at least {email, name, sub} on success, or None on failure.
    """
    try:
        if not _ALLOWED_GOOGLE_AUDS:
            logging.error("Google verification blocked: no GOOGLE_*_CLIENT_ID env vars configured.")
            return None

        r = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": token_id},
            timeout=10,
        )
        if r.status_code != 200:
            logging.warning("Google tokeninfo HTTP %s: %s", r.status_code, r.text[:200])
            return None

        data = r.json()
        aud = data.get("aud")
        iss = data.get("iss")
        exp = int(data.get("exp", "0"))
        email = data.get("email")
        email_verified_raw = data.get("email_verified")

        email_verified = (email_verified_raw in (True, "true", "1", 1))
        issuer_ok = iss in ("accounts.google.com", "https://accounts.google.com")
        not_expired = exp > int(time.time())
        aud_ok = aud in _ALLOWED_GOOGLE_AUDS

        if not (issuer_ok and not_expired and aud_ok and email and email_verified):
            logging.warning(
                "Google token rejected. issuer_ok=%s, not_expired=%s, aud_ok=%s, email=%s, email_verified=%s",
                issuer_ok, not_expired, aud_ok, bool(email), email_verified,
            )
            return None

        name = data.get("name") or data.get("given_name") or "Google User"
        return {"email": email, "name": name, "sub": data.get("sub")}
    except Exception:
        logging.exception("Google token verification failed with exception")
        return None


# =========
# APPLE
# =========

# Simple in-memory cache of Apple JWKS (public keys)
_APPLE_JWKS_CACHE = {"by_kid": {}, "expires_at": 0.0}

def _get_apple_key_for_kid(kid: str):
    now = time.time()
    if _APPLE_JWKS_CACHE["by_kid"] and _APPLE_JWKS_CACHE["expires_at"] > now:
        return _APPLE_JWKS_CACHE["by_kid"].get(kid)

    # Refresh keys (cache 12h)
    r = requests.get("https://appleid.apple.com/auth/keys", timeout=10)
    r.raise_for_status()
    jwks = r.json().get("keys", [])
    by_kid = {k["kid"]: k for k in jwks if "kid" in k}
    _APPLE_JWKS_CACHE["by_kid"] = by_kid
    _APPLE_JWKS_CACHE["expires_at"] = now + 60 * 60 * 12
    return by_kid.get(kid)

def verify_apple_token(identity_token: str) -> Optional[Dict]:
    """
    Verifies an Apple Sign-In identity token (JWT).
    Returns dict with at least {email?, name?, sub} on success, or None on failure.
    Note: Apple only sends 'email' if you requested the 'email' scope and only reliably on first sign-in.
    """
    try:
        if not _ALLOWED_APPLE_AUDS:
            logging.error("Apple verification blocked: no APPLE_BUNDLE_ID / APPLE_SERVICES_ID configured.")
            return None

        # 1) Get unverified header to find the key id (kid) & algorithm
        unverified_header = jwt.get_unverified_header(identity_token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")
        if not kid or not alg:
            logging.warning("Apple token header missing kid/alg")
            return None

        # 2) Fetch matching Apple public key (from JWKS) and convert to RSA object
        jwk = _get_apple_key_for_kid(kid)
        if not jwk:
            logging.warning("Apple JWKS did not contain key for kid=%s", kid)
            return None
        public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))

        # 3) Validate token
        #    - audience: your bundle id (iOS) and/or services id (web)
        #    - issuer: https://appleid.apple.com
        payload = jwt.decode(
            identity_token,
            key=public_key,
            algorithms=[alg],
            audience=_ALLOWED_APPLE_AUDS,
            issuer="https://appleid.apple.com",
            options={"require": ["iss", "aud", "exp", "iat"]},
        )

        # 4) Check email_verified if present
        email = payload.get("email")
        email_verified_raw = payload.get("email_verified")
        email_verified = (
            True if email_verified_raw is None else
            (email_verified_raw in (True, "true", "1", 1))
        )

        if email is None:
            # This can happen after the first login if user hides email or Apple stops sending it.
            # Your flow can fall back to an email captured earlier on first sign-in.
            logging.info("Apple token valid but no email claim present (sub=%s)", payload.get("sub"))

        if email is not None and not email_verified:
            logging.warning("Apple email present but not verified")
            return None

        name = payload.get("name") or "Apple User"
        return {"email": email, "name": name, "sub": payload.get("sub")}
    except jwt.ExpiredSignatureError:
        logging.warning("Apple token expired")
        return None
    except jwt.InvalidTokenError as e:
        logging.warning("Apple token invalid: %s", str(e))
        return None
    except Exception:
        logging.exception("Apple token verification failed with exception")
        return None
