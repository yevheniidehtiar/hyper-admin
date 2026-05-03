"""Tests for MFA fields on the User model (C1-C, #483).

Maps the BDD scenarios from the story
``.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/
featauth-add-mfa-fields-to-user-model.md`` 1:1 to test functions.

Spec: docs/specs/object-permissions-mfa.md (Track B, "Data Model Changes").
"""

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select


@pytest.fixture
def engine(tmp_path):
    # Import models so their tables register on SQLModel.metadata before create_all().
    import hyperadmin.auth.models  # noqa: F401

    db_file = tmp_path / "test_user_mfa.db"
    eng = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


def test_new_user_has_mfa_disabled_by_default(session: Session) -> None:
    """
    Scenario: new user has MFA disabled by default
      Given a new User record is created
      When  the user's fields are inspected
      Then  ``mfa_enabled`` is ``False`` and ``mfa_method`` is ``None``
    """
    from hyperadmin.auth.models import User

    # Given a new User record is created
    user = User(
        username="defaults_mfa",
        email="defaults_mfa@example.com",
        password_hash="fakehash",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # When the user's fields are inspected
    # Then mfa_enabled is False and mfa_method is None
    assert user.mfa_enabled is False
    assert user.mfa_method is None


def test_mfa_fields_are_persisted(session: Session) -> None:
    """
    Scenario: MFA fields are persisted
      Given user "alice" enables MFA with method "email"
      When  the user record is saved and reloaded
      Then  ``mfa_enabled`` is ``True`` and ``mfa_method`` is ``"email"``
    """
    from hyperadmin.auth.models import User

    # Given user "alice" enables MFA with method "email"
    alice = User(
        username="alice",
        email="alice@example.com",
        password_hash="fakehash",
        mfa_enabled=True,
        mfa_method="email",
    )
    session.add(alice)
    session.commit()

    # When the user record is saved and reloaded
    session.expire_all()
    reloaded = session.exec(select(User).where(User.username == "alice")).one()

    # Then mfa_enabled is True and mfa_method is "email"
    assert reloaded.mfa_enabled is True
    assert reloaded.mfa_method == "email"
