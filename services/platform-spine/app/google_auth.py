"""Verifying a Google ID token.

The app signs the user in with Google and sends us the resulting ID token (a
JWT signed by Google with RS256). We never trust it until we have checked:
  - the signature, against Google's published public keys (fetched from
    GOOGLE_JWKS_URL and cached by PyJWKClient),
  - `aud`: it was issued to one of OUR OAuth client IDs (GOOGLE_CLIENT_IDS),
    otherwise a token minted for some other app could sign in here,
  - `iss`: it came from Google,
  - `exp`: it has not expired,
  - `email_verified`: Google has confirmed the user owns that email.

GOOGLE_CLIENT_IDS is a comma-separated list: the Web client ID (browser and
Expo web) plus the Android client ID (the installed app). With none set,
Google sign-in is off and the endpoint answers 503.
"""

import os

import jwt

GOOGLE_JWKS_URL = os.getenv("GOOGLE_JWKS_URL", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleNotConfigured(Exception):
    """GOOGLE_CLIENT_IDS is empty: Google sign-in is switched off."""


class GoogleTokenInvalid(Exception):
    """The ID token failed verification (bad signature, audience, issuer, expiry...)."""


class GoogleUnavailable(Exception):
    """Could not fetch Google's signing keys (network problem), so we cannot tell."""


def allowed_audiences() -> list[str]:
    return [c.strip() for c in os.getenv("GOOGLE_CLIENT_IDS", "").split(",") if c.strip()]


def is_configured() -> bool:
    return bool(allowed_audiences())


_jwks_client = None


def _signing_key(token: str):
    """The public key Google signed this token with. Its own function so the
    tests can supply a key without touching the network."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600, timeout=5)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_google_id_token(token: str) -> dict:
    """Returns the verified claims. Raises GoogleNotConfigured,
    GoogleUnavailable or GoogleTokenInvalid."""
    audiences = allowed_audiences()
    if not audiences:
        raise GoogleNotConfigured("GOOGLE_CLIENT_IDS is not set")
    try:
        key = _signing_key(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=list(GOOGLE_ISSUERS),
            leeway=10,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise GoogleUnavailable(str(exc)) from exc
    except jwt.PyJWTError as exc:
        raise GoogleTokenInvalid(str(exc)) from exc
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise GoogleTokenInvalid("Google has not verified this email address")
    return claims
