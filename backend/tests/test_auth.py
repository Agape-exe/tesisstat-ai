import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClientConnectionError, PyJWKClientError

from app.authenticated_app import create_authenticated_app
from app.core.config import Settings
from app.shared.adapters.supabase_auth import SupabaseIdentityProvider
from app.shared.auth import (
    AuthenticationError,
    IdentityProviderUnavailable,
    Principal,
    ProjectAccess,
    ProjectNotFound,
    ProjectOwner,
)


class StaticJwks:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token: str):
        return SimpleNamespace(key=self.key)


class OfflineJwks:
    def get_signing_key_from_jwt(self, token: str):
        raise PyJWKClientConnectionError("offline")


class UnknownKeyJwks:
    def get_signing_key_from_jwt(self, token: str):
        raise PyJWKClientError('Unable to find a signing key that matches: "unknown"')


def auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_audience="authenticated",
        supabase_jwt_algorithms=["RS256"],
    )


def signed_token(private_key, subject: UUID, *, kid: str | None = "test-key", **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(subject),
        "role": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    headers = {"kid": kid} if kid is not None else None
    return jwt.encode(claims, private_key, algorithm="RS256", headers=headers)


@pytest.fixture
def key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def test_supabase_provider_returns_only_verified_uuid_subject(key_pair):
    private_key, public_key = key_pair
    subject = uuid4()
    provider = SupabaseIdentityProvider(auth_settings(), jwks_client=StaticJwks(public_key))

    assert asyncio.run(provider.resolve_user(signed_token(private_key, subject))) == str(subject)


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "anon"},
        {"aud": "other"},
        {"iss": "https://attacker.invalid/auth/v1"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"sub": "not-a-uuid"},
    ],
)
def test_supabase_provider_rejects_invalid_claims(key_pair, overrides):
    private_key, public_key = key_pair
    provider = SupabaseIdentityProvider(auth_settings(), jwks_client=StaticJwks(public_key))

    with pytest.raises(AuthenticationError):
        asyncio.run(provider.resolve_user(signed_token(private_key, uuid4(), **overrides)))


def test_supabase_provider_fails_closed_when_jwks_is_unavailable(key_pair):
    private_key, _ = key_pair
    provider = SupabaseIdentityProvider(auth_settings(), jwks_client=OfflineJwks())

    with pytest.raises(IdentityProviderUnavailable):
        asyncio.run(provider.resolve_user(signed_token(private_key, uuid4())))


def test_supabase_provider_rejects_missing_or_unknown_signing_key(key_pair):
    private_key, public_key = key_pair
    without_kid = SupabaseIdentityProvider(auth_settings(), jwks_client=StaticJwks(public_key))
    unknown_kid = SupabaseIdentityProvider(auth_settings(), jwks_client=UnknownKeyJwks())

    with pytest.raises(AuthenticationError):
        asyncio.run(without_kid.resolve_user(signed_token(private_key, uuid4(), kid=None)))
    with pytest.raises(AuthenticationError):
        asyncio.run(unknown_kid.resolve_user(signed_token(private_key, uuid4(), kid="unknown")))


class FakeIdentityProvider:
    def __init__(self, subject: UUID):
        self.subject = subject

    async def resolve_user(self, access_token: str) -> str:
        if access_token == "valid-token":
            return str(self.subject)
        if access_token == "offline-token":
            raise IdentityProviderUnavailable("offline")
        raise AuthenticationError("invalid")


def test_auth_http_contract_distinguishes_missing_invalid_and_unavailable_provider():
    subject = uuid4()
    app = create_authenticated_app(
        Settings(_env_file=None), identity_provider=FakeIdentityProvider(subject)
    )
    client = TestClient(app)

    missing = client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"

    invalid = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "invalid bearer token"}

    offline = client.get("/auth/me", headers={"Authorization": "Bearer offline-token"})
    assert offline.status_code == 503
    assert offline.json() == {"detail": "identity provider unavailable"}

    verified = client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
    assert verified.status_code == 200
    assert verified.json() == {"subject": str(subject), "mode": "authenticated"}


def test_authenticated_app_refuses_to_start_without_identity_configuration():
    with pytest.raises(ValueError, match="issuer, audience and JWKS URL"):
        create_authenticated_app(Settings(_env_file=None))


class OwnershipFixture:
    def __init__(self, owners: dict[UUID, UUID | None]):
        self.owners = owners

    def find_owner(self, project_id: UUID) -> ProjectOwner | None:
        if project_id not in self.owners:
            return None
        return ProjectOwner(id=project_id, owner_id=self.owners[project_id])

    def list_owned(self, owner_id: UUID) -> list[UUID]:
        return [project_id for project_id, owner in self.owners.items() if owner == owner_id]


def test_project_access_never_releases_another_users_project():
    owner_a, owner_b = uuid4(), uuid4()
    project_a, project_b = uuid4(), uuid4()
    access = ProjectAccess(OwnershipFixture({project_a: owner_a, project_b: owner_b}))
    principal_a = Principal(subject=owner_a, mode="authenticated")

    assert access.require(principal_a, project_a).owner_id == owner_a
    assert [item.id for item in access.list_owned(principal_a)] == [project_a]
    with pytest.raises(ProjectNotFound, match="project not found"):
        access.require(principal_a, project_b)
    with pytest.raises(ProjectNotFound, match="project not found"):
        access.require(principal_a, uuid4())
