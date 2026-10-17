"""The simple example stamps aware UTC creation times (st-v058-byoa-48).

sqlmodel >= 0.0.45 maps ``datetime`` fields to ``UTCDateTime``, which rejects
naive values, so ``default_factory=datetime.now`` breaks every insert. The
example models use :func:`hyperadmin.core.utc_now` instead, which works on both
sides of the former ``<0.0.45`` cap.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from examples.simple.models import Product, User
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from hyperadmin.core import utc_now
from hyperadmin.core.timezones import is_auto_now_factory


def test_example_models_default_to_utc_now() -> None:
    """
    Scenario: example timestamps use utc_now
      Given the simple example's User and Product models
      When  their datetime defaults are inspected
      Then  both default factories are utc_now
      And   the admin still treats them as auto-now fields
    """
    user_factory = User.model_fields["created_at"].default_factory
    product_factory = Product.model_fields["release_date"].default_factory

    assert user_factory is utc_now
    assert product_factory is utc_now
    assert is_auto_now_factory(user_factory)
    assert is_auto_now_factory(product_factory)


def test_example_models_stamp_aware_utc_values() -> None:
    """
    Scenario: new example rows carry an aware UTC timestamp
      Given the simple example's User and Product models
      When  an instance is built without timestamps
      Then  created_at and release_date are aware with a zero UTC offset
    """
    user = User(name="Ada")
    product = Product(name="Lamp", price=1.0)

    assert user.created_at is not None
    assert user.created_at.utcoffset() == timedelta(0)
    assert product.release_date is not None
    assert product.release_date.utcoffset() == timedelta(0)


def test_example_user_insert_succeeds(tmp_path: Path) -> None:
    """
    Scenario: inserting an example row succeeds on the installed sqlmodel
      Given a fresh SQLite database with the example User table
      When  a User is inserted with its default created_at
      Then  the row is stored and read back with its creation time
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'example.db'}")
    SQLModel.metadata.create_all(engine, tables=[User.__table__])  # type: ignore[attr-defined]

    with Session(engine) as session:
        session.add(User(name="Ada"))
        session.commit()

    with Session(engine) as session:
        stored = session.exec(select(User).where(User.name == "Ada")).one()

    assert stored.created_at is not None
