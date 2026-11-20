"""``OAuthToken`` model, token cipher and unusable passwords (#439, docs/specs/oauth-sso.md)."""

from __future__ import annotations

import builtins
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from hyperadmin.auth.backend import (
    hash_password,
    is_password_usable,
    make_unusable_password,
    verify_password,
)
from hyperadmin.auth.exceptions import OAuthConfigError
from hyperadmin.auth.models import OAuthToken, User
from hyperadmin.auth.oauth import tokens as tokens_module
from hyperadmin.auth.oauth.tokens import (
    TOKEN_SECRET_ENV,
    FernetTokenCipher,
    configure_token_cipher,
    token_cipher,
)


@pytest.fixture(autouse=True)
def _cipher() -> Iterator[None]:
    configure_token_cipher(Fernet.generate_key().decode())
    yield
    configure_token_cipher(None)


@pytest.fixture
def session(tmp_path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'oauth.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def alice(session: Session) -> User:
    user = User(username="alice", email="alice@acme.com", password_hash=hash_password("secret"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _token(user: User, provider: str = "google", sub: str = "abc123", **extra) -> OAuthToken:
    assert user.id is not None
    return OAuthToken(user_id=user.id, provider=provider, sub=sub, **extra)


# ── Model ─────────────────────────────────────────────────────────────────


def test_oauth_token_stores_provider_credentials_for_a_user(session: Session, alice: User) -> None:
    """
    Scenario: OAuthToken stores provider credentials for a user
      Given user alice authenticated via Google
      When  an OAuthToken is created with provider="google" and access_token="abc123"
      Then  the token is persisted with user_id = alice.id
    """
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    session.add(
        _token(
            alice,
            access_token="abc123",
            refresh_token="refresh-1",
            expires_at=expires,
            scopes=["openid", "email"],
        )
    )
    session.commit()
    session.expire_all()

    stored = session.exec(select(OAuthToken)).one()
    assert stored.user_id == alice.id
    assert stored.provider == "google"
    assert stored.access_token == "abc123"
    assert stored.refresh_token == "refresh-1"
    assert stored.scopes == ["openid", "email"]
    assert stored.expires_at is not None
    assert abs(stored.expires_at - expires) < timedelta(seconds=1)
    assert stored.created_at.tzinfo is not None
    assert stored.user is not None
    assert stored.user.username == "alice"
    assert str(stored) == "google:abc123"


def test_oauth_token_supports_multiple_providers_per_user(session: Session, alice: User) -> None:
    """
    Scenario: OAuthToken supports multiple providers per user
      Given user alice has a Google token
      When  a GitHub token is also created for alice
      Then  alice has 2 OAuthToken records with different providers
    """
    session.add(_token(alice, access_token="g"))
    session.commit()

    session.add(_token(alice, provider="github", sub="42", access_token="h"))
    session.commit()

    rows = session.exec(select(OAuthToken).where(OAuthToken.user_id == alice.id)).all()
    assert sorted(row.provider for row in rows) == ["github", "google"]


def test_one_identity_per_provider_and_user(session: Session, alice: User) -> None:
    session.add(_token(alice, access_token="g"))
    session.commit()

    session.add(_token(alice, sub="other", access_token="g2"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_one_user_per_provider_identity(session: Session, alice: User) -> None:
    bob = User(username="bob", email="bob@acme.com", password_hash="x")
    session.add_all([bob, _token(alice, access_token="g")])
    session.commit()

    session.add(_token(bob, access_token="g2"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_oauth_tokens_are_encrypted_at_rest(session: Session, alice: User) -> None:
    """
    Scenario: OAuth tokens are encrypted at rest
      Given an OAuthToken row exists for alice
      When  the access_token field is read directly from the database
      Then  the stored bytes are not equal to the plaintext access_token
      And   reading via OAuthToken.access_token returns the plaintext
    """
    session.add(_token(alice, access_token="plain-access", refresh_token="plain-refresh"))
    session.commit()

    raw_access, raw_refresh = session.execute(
        text("SELECT access_token_encrypted, refresh_token_encrypted FROM hyperadmin_oauth_tokens")
    ).one()
    assert b"plain-access" not in bytes(raw_access)
    assert b"plain-refresh" not in bytes(raw_refresh)
    session.expire_all()
    stored = session.exec(select(OAuthToken)).one()
    assert stored.access_token == "plain-access"
    assert stored.refresh_token == "plain-refresh"


def test_refresh_token_is_optional(alice: User) -> None:
    token = _token(alice, access_token="a")

    assert token.refresh_token is None
    token.refresh_token = "r"
    assert token.refresh_token == "r"
    token.refresh_token = None
    assert token.refresh_token_encrypted is None


def test_the_token_table_is_part_of_the_built_in_metadata() -> None:
    import hyperadmin.auth

    assert "hyperadmin_oauth_tokens" in hyperadmin.auth.metadata().tables


# ── Unusable passwords ────────────────────────────────────────────────────


def test_an_unusable_password_matches_no_password() -> None:
    marker = make_unusable_password()

    assert marker != make_unusable_password()
    assert is_password_usable(marker) is False
    assert verify_password("", marker) is False
    assert verify_password(marker, marker) is False
    assert verify_password(marker[1:], marker) is False


def test_real_hashes_are_usable_and_empty_ones_are_not() -> None:
    assert is_password_usable(hash_password("secret")) is True
    assert is_password_usable("") is False
    assert is_password_usable(None) is False


def test_user_oauth_only_follows_the_password_hash() -> None:
    local = User(username="a", email="a@acme.com", password_hash=hash_password("secret"))
    federated = User(username="b", email="b@acme.com", password_hash=make_unusable_password())

    assert local.oauth_only is False
    assert federated.oauth_only is True


# ── Cipher ────────────────────────────────────────────────────────────────


def test_cipher_round_trips_and_never_returns_plaintext() -> None:
    cipher = FernetTokenCipher(Fernet.generate_key().decode())

    ciphertext = cipher.encrypt("s3cr3t")

    assert b"s3cr3t" not in ciphertext
    assert cipher.decrypt(ciphertext) == "s3cr3t"


def test_key_rotation_decrypts_with_any_key_and_encrypts_with_the_first() -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    written_with_old = FernetTokenCipher(old).encrypt("token")

    rotated = FernetTokenCipher(f"{new}, {old}")

    assert rotated.decrypt(written_with_old) == "token"
    assert FernetTokenCipher(new).decrypt(rotated.encrypt("fresh")) == "fresh"


def test_a_replaced_key_reports_a_configuration_error() -> None:
    ciphertext = FernetTokenCipher(Fernet.generate_key().decode()).encrypt("token")

    with pytest.raises(OAuthConfigError, match="cannot be decrypted"):
        FernetTokenCipher(Fernet.generate_key().decode()).decrypt(ciphertext)


@pytest.mark.parametrize("secret", ["", " , "])
def test_a_missing_key_is_rejected(secret: str) -> None:
    with pytest.raises(OAuthConfigError, match=TOKEN_SECRET_ENV):
        FernetTokenCipher(secret)


def test_a_malformed_key_is_rejected() -> None:
    with pytest.raises(OAuthConfigError, match="invalid Fernet key"):
        FernetTokenCipher("not-a-fernet-key")


def test_a_missing_cryptography_package_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name.startswith("cryptography"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(OAuthConfigError, match=r"hyper-admin\[oauth\]"):
        FernetTokenCipher(Fernet.generate_key().decode())


def test_token_cipher_falls_back_to_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    configure_token_cipher(None)
    monkeypatch.setenv(TOKEN_SECRET_ENV, key)

    cipher = token_cipher()

    assert FernetTokenCipher(key).decrypt(cipher.encrypt("x")) == "x"
    assert token_cipher() is cipher


def test_token_cipher_without_any_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_token_cipher(None)
    monkeypatch.delenv(TOKEN_SECRET_ENV, raising=False)

    with pytest.raises(OAuthConfigError):
        token_cipher()
    assert tokens_module._configured == []


def test_importing_the_models_does_not_import_cryptography() -> None:
    code = (
        "import sys\n"
        "import hyperadmin.auth.models, hyperadmin.auth.oauth\n"
        "print('cryptography' in sys.modules, 'httpx_oauth' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False False"


def test_unknown_oauth_export_raises_attribute_error() -> None:
    from hyperadmin.auth import oauth

    with pytest.raises(AttributeError, match="no_such_name"):
        oauth.no_such_name  # noqa: B018 - attribute access is the behaviour under test
    assert "token_cipher" in dir(oauth)
    assert oauth.token_cipher is token_cipher
