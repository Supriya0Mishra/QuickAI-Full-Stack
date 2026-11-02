"""Clerk authentication.

The React app sends `Authorization: Bearer <token>`, where the token is a Clerk
session JWT (from `getToken()`). We verify it ourselves:

- signature: RS256 only, with Clerk's public keys (JWKS), cached in memory
- claims: not expired, issued by our Clerk instance, used by an allowed frontend

Route code then gets a `CurrentUser` from the `get_current_user` dependency.
"""

import asyncio
import base64
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"


def unauthorized(message: str = "Please sign in to continue.") -> AppError:
    return AppError(401, message)


def auth_unavailable() -> AppError:
    return AppError(503, "Sign-in is temporarily unavailable. Please try again.")


def frontend_api_from_publishable_key(publishable_key: str) -> str:
    """Clerk publishable keys are `pk_test_` / `pk_live_` + base64("<frontend-api>$")."""
    for prefix in ("pk_test_", "pk_live_"):
        if publishable_key.startswith(prefix):
            encoded = publishable_key.removeprefix(prefix)
            break
    else:
        raise ValueError("Not a Clerk publishable key (must start with pk_test_ or pk_live_)")
    if not encoded:
        raise ValueError("Not a Clerk publishable key")
    decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    if not decoded.endswith("$") or len(decoded) < 2:
        raise ValueError("Not a Clerk publishable key")
    return decoded[:-1]


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    plan: str  # "free", or the Clerk Billing plan slug, e.g. "premium"
    session_id: str | None = None

    @property
    def is_premium(self) -> bool:
        return self.plan == "premium"


def plan_from_claims(claims: dict[str, Any]) -> str:
    """Clerk Billing puts the active plan in the `pla` claim: "u:<slug>" for a
    user plan, "o:<slug>" for an organization plan. Anything else means free."""
    pla = claims.get("pla")
    if isinstance(pla, str) and pla.startswith("u:") and len(pla) > 2:
        return pla[2:]
    return "free"


class JWKSCache:
    """Clerk's public keys, fetched once and reused.

    Refetches when the cache is older than `ttl`, or when a token uses a key id
    we don't know yet (Clerk rotated its keys). Fetch attempts, successful or
    not, happen at most once per `min_refresh_interval`, so junk tokens can't make
    us hammer Clerk and an outage doesn't make every request wait for a timeout.
    If Clerk is unreachable, keys we already have keep working.
    """

    def __init__(
        self,
        url: str,
        http: httpx.AsyncClient | None = None,
        ttl: float = 3600,
        min_refresh_interval: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.url = url
        self._http = http
        self._ttl = ttl
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None  # last successful fetch
        self._attempted_at: float | None = None  # last fetch attempt, success or not
        self._last_attempt_ok = False
        self._lock = asyncio.Lock()

    def _since(self, moment: float | None) -> float:
        return float("inf") if moment is None else self._clock() - moment

    async def get_key(self, kid: str) -> jwt.PyJWK:
        if kid in self._keys and self._since(self._fetched_at) < self._ttl:
            return self._keys[kid]

        if self._since(self._attempted_at) >= self._min_refresh_interval:
            await self._refresh()

        if kid in self._keys:
            if self._since(self._fetched_at) >= self._ttl:
                logger.warning("Using cached Clerk keys; refresh failed")
            return self._keys[kid]
        if not self._last_attempt_ok:
            raise auth_unavailable()  # we have no keys because Clerk is unreachable
        raise unauthorized()  # Clerk answered; this key id doesn't exist

    async def _refresh(self) -> None:
        """Fetch the keys. Never raises; the outcome is recorded instead."""
        async with self._lock:
            # Another request may have tried while we waited for the lock.
            if self._since(self._attempted_at) < self._min_refresh_interval:
                return
            self._attempted_at = self._clock()
            if self._http is None:
                self._http = httpx.AsyncClient(timeout=5)
            try:
                response = await self._http.get(self.url)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
                    raise ValueError("JWKS response has no 'keys' list")
            except (httpx.HTTPError, ValueError):
                logger.exception("Could not fetch Clerk JWKS from %s", self.url)
                self._last_attempt_ok = False
                return

            keys: dict[str, jwt.PyJWK] = {}
            for key in data["keys"]:
                if not isinstance(key, dict) or not key.get("kid") or key.get("kty") != "RSA":
                    continue
                try:
                    keys[key["kid"]] = jwt.PyJWK(key, algorithm=ALGORITHM)
                except (jwt.PyJWKError, jwt.InvalidKeyError):
                    # One bad key must not block the valid ones.
                    logger.warning("Skipping invalid Clerk key %s", key.get("kid"))
            self._keys = keys
            self._fetched_at = self._clock()
            self._last_attempt_ok = True


class ClerkVerifier:
    def __init__(
        self,
        issuer: str,
        authorized_parties: list[str],
        jwks: JWKSCache | None = None,
        pem_key: str | None = None,
        leeway: float = 5,
    ):
        if jwks is None and not pem_key:
            raise ValueError("Need a JWKS cache or a PEM key")
        self.issuer = issuer
        self.authorized_parties = authorized_parties
        self.jwks = jwks
        self.pem_key = pem_key
        self.leeway = leeway

    async def verify(self, token: str) -> CurrentUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError:
            raise unauthorized() from None

        # Reject anything but RS256 before touching keys. This blocks
        # "alg: none" tokens and HS256 tokens signed with the public key.
        if header.get("alg") != ALGORITHM:
            raise unauthorized()

        if self.pem_key:
            key: Any = self.pem_key
        else:
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise unauthorized()
            key = (await self.jwks.get_key(kid)).key

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iat", "iss", "sub"], "verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            raise unauthorized("Your session has expired. Please sign in again.") from None
        except jwt.InvalidTokenError:
            raise unauthorized() from None

        azp = claims.get("azp")
        if azp and self.authorized_parties and azp not in self.authorized_parties:
            raise unauthorized()

        return CurrentUser(
            user_id=claims["sub"],
            plan=plan_from_claims(claims),
            session_id=claims.get("sid"),
        )


@lru_cache
def build_verifier() -> ClerkVerifier | None:
    """Built once. Returns None (and logs once) if Clerk isn't configured."""
    settings = get_settings()
    try:
        frontend_api = frontend_api_from_publishable_key(settings.clerk_publishable_key)
    except ValueError:
        logger.error("CLERK_PUBLISHABLE_KEY is missing or invalid; sign-in will return 503")
        return None

    issuer = f"https://{frontend_api}"
    if settings.clerk_jwt_key:
        return ClerkVerifier(issuer, settings.authorized_party_list, pem_key=settings.clerk_jwt_key)
    return ClerkVerifier(
        issuer,
        settings.authorized_party_list,
        jwks=JWKSCache(f"{issuer}/.well-known/jwks.json"),
    )


def get_verifier() -> ClerkVerifier:
    """FastAPI dependency (overridable in tests)."""
    verifier = build_verifier()
    if verifier is None:
        raise auth_unavailable()
    return verifier


_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[ClerkVerifier, Depends(get_verifier)],
) -> CurrentUser:
    """FastAPI dependency: the signed-in user, or a 401 error."""
    if credentials is None:
        raise unauthorized()
    return await verifier.verify(credentials.credentials)
