"""get_display_name skips descriptive attributes it cannot read on a detached row (#773)."""

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from hyperadmin.core.display import get_display_name


class _Base(DeclarativeBase):
    pass


class DispLabel(_Base):
    __tablename__ = "disp_label"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(20))


class DispFood(_Base):
    __tablename__ = "disp_food"

    id: Mapped[int] = mapped_column(primary_key=True)
    label_id: Mapped[int | None] = mapped_column(ForeignKey("disp_label.id"))
    label: Mapped[DispLabel | None] = relationship(DispLabel)
    name: Mapped[str | None] = mapped_column(String(20))


def test_lazy_relationship_named_like_a_descriptive_attribute_is_skipped() -> None:
    """
    Scenario: an unloadable descriptive attribute is skipped
      Given a model whose label is a lazy relationship and whose row is detached
      When  get_display_name runs
      Then  it moves on to the next candidate instead of raising
    """
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(DispLabel(id=7, text="spice"))
        session.add(DispFood(id=1, name=None, label_id=7))
        session.commit()
        session.expire_all()
        food = session.get(DispFood, 1)
        assert food is not None
    session.close()

    assert get_display_name(food) == "DispFood (1)"
