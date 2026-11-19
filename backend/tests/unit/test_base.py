from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase
from src.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class _Sample(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sample"


class _CreatedOnly(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "created_only_sample"


def test_base_is_declarative_base() -> None:
    assert issubclass(Base, DeclarativeBase)


def test_naming_convention_is_defined() -> None:
    convention = Base.metadata.naming_convention
    assert set(convention) >= {"ix", "uq", "ck", "fk", "pk"}


def test_uuid_primary_key_mixin() -> None:
    column = _Sample.__table__.c.id
    assert column.primary_key
    assert isinstance(column.type, Uuid)
    assert column.server_default is not None


def test_timestamp_mixin_columns_are_timezone_aware() -> None:
    for name in ("created_at", "updated_at"):
        column = _Sample.__table__.c[name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is False


def test_created_at_mixin_adds_only_created_at() -> None:
    table = _CreatedOnly.__table__
    assert set(table.c.keys()) == {"id", "created_at"}
    created_at = table.c.created_at
    assert isinstance(created_at.type, DateTime)
    assert created_at.type.timezone is True
    assert created_at.nullable is False
    assert created_at.server_default is not None
    assert created_at.onupdate is None


def test_timestamp_mixin_extends_created_at_mixin_with_updated_at() -> None:
    assert issubclass(TimestampMixin, CreatedAtMixin)
    assert set(_Sample.__table__.c.keys()) == {"id", "created_at", "updated_at"}
