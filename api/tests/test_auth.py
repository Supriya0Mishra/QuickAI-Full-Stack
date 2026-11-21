"""Clerk token verification, with real RSA keys and a fake Clerk JWKS endpoint."""

import base64
import hashlib
import hmac
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.auth import (
    ClerkVerifier,
    JWKSCache,
    build_verifier,
    frontend_api_from_publishable_key,
    get_verifier,
)
from app.core.config import get_settings
from app.main import create_app
from tests.conftest import request

FRONTEND_API = "clean-cat-12.clerk.accounts.dev"
ISSUER = f"https://{FRONTEND_API}"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
CLIENT = "http://localhost:5173"

CLERK_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ROTATED_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ATTACKER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_jwk(private_key, kid: str) -> dict:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    return jwk | {"kid": kid, "alg": "RS256", "use": "sig"}


def public_pem(private_key) -> str:
    return (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


def make_token(key=CLERK_KEY, kid="key-1", **claims) -> str:
    now = int(time.time())
    payload = {
        "sub": "user_123",
        "sid": "sess_1",
        "iss": ISSUER,
        "azp": CLIENT,
        "iat": now,
        "nbf": now,
        "exp": now + 60,
    } | claims
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unsigned_token(header: dict, payload: dict, signature: bytes = b"") -> str:
    head = b64url(json.dumps(header).encode())
    body = b64url(json.dumps(payload).encode())
    return f"{head}.{body}.{b64url(signature)}"


class FakeClerk:
    """Serves a JWKS and counts requests. Set `up = False` to simulate an outage."""

    def __init__(self, keys: list[dict]):
        self.keys = keys
        self.up = True
        self.requests = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        assert str(request.url) == JWKS_URL
        if not self.up:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": self.keys})


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clerk() -> FakeClerk:
    return FakeClerk([public_jwk(CLERK_KEY, "key-1")])


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def verifier(clerk, clock) -> ClerkVerifier:
    http = httpx.AsyncClient(transport=httpx.MockTransport(clerk.handler))
    jwks = JWKSCache(JWKS_URL, http=http, ttl=3600, min_refresh_interval=30, clock=clock)
    return ClerkVerifier(ISSUER, [CLIENT], jwks=jwks)


@pytest.fixture
def app(verifier):
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    return app


async def call_me(app, token: str | None = None, scheme: str = "Bearer") -> httpx.Response:
    headers = {"Authorization": f"{scheme} {token}"} if token is not None else {}
    return await request(app, "GET", "/api/user/me", headers=headers)


# --- Publishable key -------------------------------------------------------------


def test_frontend_api_is_read_from_publishable_key():
    encoded = base64.b64encode(f"{FRONTEND_API}$".encode()).decode().rstrip("=")

    assert frontend_api_from_publishable_key(f"pk_test_{encoded}") == FRONTEND_API
    assert frontend_api_from_publishable_key(f"pk_live_{encoded}") == FRONTEND_API


VALID_ENCODED = base64.b64encode(f"{FRONTEND_API}$".encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "sk_test_abc",
        "pk_test_",
        "pk_test_bm8tZG9sbGFy",
        "hello",
        # Right encoded domain, wrong prefix (e.g. a secret key pasted by mistake)
        f"sk_test_{VALID_ENCODED}",
        f"xx_live_{VALID_ENCODED}",
    ],
)
def test_invalid_publishable_keys_are_rejected(bad):
    with pytest.raises(ValueError):
        frontend_api_from_publishable_key(bad)


# --- Valid tokens -------------------------------------------------------------------


async def test_valid_token_returns_the_user(app):
    response = await call_me(app, make_token())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "user": {"id": "user_123", "plan": "free", "is_premium": False},
    }


async def test_premium_plan_comes_from_the_pla_claim(app):
    response = await call_me(app, make_token(pla="u:premium"))

    assert response.json()["user"] == {"id": "user_123", "plan": "premium", "is_premium": True}


async def test_organization_plan_does_not_count_as_user_premium(app):
    response = await call_me(app, make_token(pla="o:premium"))

    assert response.json()["user"]["is_premium"] is False


async def test_token_without_azp_is_accepted(app):
    response = await call_me(app, make_token(azp=None))

    assert response.status_code == 200


async def test_pem_key_mode_needs_no_network():
    verifier = ClerkVerifier(ISSUER, [CLIENT], pem_key=public_pem(CLERK_KEY))

    user = await verifier.verify(make_token())

    assert user.user_id == "user_123"


# --- Rejected tokens ----------------------------------------------------------------


async def test_missing_token_is_401_with_standard_error_shape(app):
    response = await call_me(app)

    assert response.status_code == 401
    assert response.json() == {"success": False, "message": "Please sign in to continue."}


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c", ""])
async def test_garbage_token_is_401(app, token):
    response = await call_me(app, token)

    assert response.status_code == 401


async def test_non_bearer_scheme_is_401(app):
    response = await call_me(app, make_token(), scheme="Basic")

    assert response.status_code == 401


async def test_expired_token_is_401_with_clear_message(app):
    past = int(time.time()) - 3600
    response = await call_me(app, make_token(iat=past - 60, nbf=past - 60, exp=past))

    assert response.status_code == 401
    assert "expired" in response.json()["message"]


async def test_token_not_valid_yet_is_401(app):
    future = int(time.time()) + 3600
    response = await call_me(app, make_token(nbf=future, exp=future + 60))

    assert response.status_code == 401


async def test_token_from_another_clerk_instance_is_401(app):
    response = await call_me(app, make_token(iss="https://someone-else.clerk.accounts.dev"))

    assert response.status_code == 401


async def test_token_for_another_frontend_is_401(app):
    response = await call_me(app, make_token(azp="https://evil.example.com"))

    assert response.status_code == 401


async def test_token_without_user_id_is_401(app):
    response = await call_me(app, make_token(sub=None))

    assert response.status_code == 401


async def test_token_signed_with_attackers_key_is_401(app):
    # Same key id as Clerk's real key, but signed with a different private key.
    response = await call_me(app, make_token(key=ATTACKER_KEY, kid="key-1"))

    assert response.status_code == 401


async def test_alg_none_token_is_401(app):
    now = int(time.time())
    token = unsigned_token(
        {"alg": "none", "typ": "JWT", "kid": "key-1"},
        {"sub": "user_admin", "iss": ISSUER, "iat": now, "exp": now + 60},
    )

    response = await call_me(app, token)

    assert response.status_code == 401


async def test_hs256_token_signed_with_public_key_is_401(app):
    # Classic "algorithm confusion": sign with HMAC using the *public* key as the
    # secret, hoping the server verifies HS256 with the same key.
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": "key-1"}
    payload = {"sub": "user_admin", "iss": ISSUER, "iat": now, "exp": now + 60}
    signing_input = unsigned_token(header, payload).rsplit(".", 1)[0]
    signature = hmac.new(
        public_pem(CLERK_KEY).encode(), signing_input.encode(), hashlib.sha256
    ).digest()

    response = await call_me(app, f"{signing_input}.{b64url(signature)}")

    assert response.status_code == 401


# --- Key caching and rotation -----------------------------------------------------


async def test_keys_are_fetched_once_and_cached(app, clerk):
    for _ in range(5):
        assert (await call_me(app, make_token())).status_code == 200

    assert clerk.requests == 1


async def test_rotated_key_is_picked_up(app, clerk, clock):
    assert (await call_me(app, make_token())).status_code == 200

    clerk.keys = [public_jwk(CLERK_KEY, "key-1"), public_jwk(ROTATED_KEY, "key-2")]
    clock.now += 60  # past the minimum refresh interval
    response = await call_me(app, make_token(key=ROTATED_KEY, kid="key-2"))

    assert response.status_code == 200
    assert clerk.requests == 2


async def test_unknown_key_ids_cannot_make_us_spam_clerk(app, clerk):
    assert (await call_me(app, make_token())).status_code == 200

    for i in range(10):
        response = await call_me(app, make_token(kid=f"junk-{i}"))
        assert response.status_code == 401

    assert clerk.requests == 1  # no refetch within the minimum refresh interval


async def test_clerk_down_with_no_cached_keys_is_503(app, clerk):
    clerk.up = False

    response = await call_me(app, make_token())

    assert response.status_code == 503
    assert response.json()["success"] is False


async def test_clerk_down_after_cache_expiry_keeps_using_cached_keys(app, clerk, clock):
    assert (await call_me(app, make_token())).status_code == 200

    clerk.up = False
    clock.now += 7200  # cache is past its TTL, so it tries to refresh and fails
    response = await call_me(app, make_token())

    assert response.status_code == 200
    assert clerk.requests == 2


async def test_clerk_outage_does_not_retry_on_every_request(app, clerk, clock):
    # Review fix: a failed refresh used to be retried by every request, each one
    # waiting for the timeout. Now one attempt per minimum refresh interval.
    assert (await call_me(app, make_token())).status_code == 200
    clerk.up = False
    clock.now += 7200

    for _ in range(5):
        assert (await call_me(app, make_token())).status_code == 200

    assert clerk.requests == 2  # the initial fetch + one failed refresh

    clock.now += 60  # interval passed: one more attempt is allowed
    assert (await call_me(app, make_token())).status_code == 200
    assert clerk.requests == 3


async def test_clerk_down_with_no_keys_stays_503_without_retry_storm(app, clerk):
    clerk.up = False

    for _ in range(5):
        assert (await call_me(app, make_token())).status_code == 503

    assert clerk.requests == 1


async def test_one_malformed_key_does_not_block_valid_keys(app, clerk):
    # Review fix: a key PyJWT can't load used to crash the refresh with a 500.
    broken = {"kid": "broken", "kty": "RSA", "alg": "RS256", "e": "AQAB"}  # no "n"
    clerk.keys = [broken, public_jwk(CLERK_KEY, "key-1")]

    response = await call_me(app, make_token())

    assert response.status_code == 200


async def test_malformed_jwks_response_is_503_not_500(app, clerk):
    clerk.keys = None  # Clerk answers {"keys": null}

    response = await call_me(app, make_token())

    assert response.status_code == 503


# --- Configuration ------------------------------------------------------------------


@pytest.fixture
def clean_settings(monkeypatch):
    get_settings.cache_clear()
    build_verifier.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()
    build_verifier.cache_clear()


async def test_missing_clerk_configuration_is_503_not_500(clean_settings):
    clean_settings.setenv("CLERK_PUBLISHABLE_KEY", "")

    response = await call_me(create_app(), make_token())

    assert response.status_code == 503


async def test_missing_clerk_configuration_is_logged_once(clean_settings, caplog):
    # Review fix: the error used to be logged on every request.
    clean_settings.setenv("CLERK_PUBLISHABLE_KEY", "")
    app = create_app()

    for _ in range(3):
        assert (await call_me(app, make_token())).status_code == 503

    errors = [r for r in caplog.records if "CLERK_PUBLISHABLE_KEY" in r.getMessage()]
    assert len(errors) == 1


async def test_pem_key_with_escaped_newlines_works(clean_settings):
    # Review fix: one-line PEMs ("\n" as two characters) from env files used to fail.
    one_line_pem = public_pem(CLERK_KEY).strip().replace("\n", "\\n")
    clean_settings.setenv("CLERK_PUBLISHABLE_KEY", f"pk_test_{VALID_ENCODED}")
    clean_settings.setenv("CLERK_JWT_KEY", one_line_pem)

    response = await call_me(create_app(), make_token())

    assert response.status_code == 200
    assert response.json()["user"]["id"] == "user_123"
