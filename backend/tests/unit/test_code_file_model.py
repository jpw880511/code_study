import uuid
from typing import Any, cast

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Table, Text, Uuid
from sqlalchemy.orm import class_mapper
from sqlalchemy.schema import DefaultClause
from src.models import Base, CodeFile, UploadedCode
from src.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin
from src.models.code_file import SUPPORTED_EXTENSIONS

TABLE = cast(Table, CodeFile.__table__)


def column(name: str) -> Column[Any]:
    return TABLE.c[name]


def default_sql(name: str) -> str:
    server_default = column(name).server_default
    assert isinstance(server_default, DefaultClause)
    return str(server_default.arg)


def test_registered_on_the_shared_metadata() -> None:
    assert CodeFile.__tablename__ == "code_files"
    assert Base.metadata.tables["code_files"] is TABLE
    assert issubclass(CodeFile, UUIDPrimaryKeyMixin)
    assert issubclass(CodeFile, CreatedAtMixin)


def test_columns_match_the_migration() -> None:
    assert set(TABLE.c.keys()) == {
        "id",
        "uploaded_code_id",
        "file_name",
        "file_path",
        "file_extension",
        "file_size_bytes",
        "storage_path",
        "mime_type",
        "created_at",
    }


def test_primary_key_is_a_database_generated_uuid() -> None:
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]
    assert isinstance(column("id").type, Uuid)
    assert "gen_random_uuid()" in default_sql("id")


def test_uploaded_code_id_is_a_required_foreign_key_that_cascades_on_delete() -> None:
    uploaded_code_id = column("uploaded_code_id")
    assert isinstance(uploaded_code_id.type, Uuid)
    assert uploaded_code_id.nullable is False
    (foreign_key,) = uploaded_code_id.foreign_keys
    assert foreign_key.target_fullname == "uploaded_code.id"
    assert foreign_key.ondelete == "CASCADE"


def test_file_name_and_storage_path_are_required() -> None:
    file_name = column("file_name")
    assert isinstance(file_name.type, String)
    assert file_name.type.length == 255
    assert file_name.nullable is False
    storage_path = column("storage_path")
    assert isinstance(storage_path.type, Text)
    assert storage_path.nullable is False


def test_the_other_descriptive_columns_are_optional() -> None:
    assert isinstance(column("file_path").type, Text)
    extension = column("file_extension")
    assert isinstance(extension.type, String)
    assert extension.type.length == 20
    assert isinstance(column("file_size_bytes").type, Integer)
    mime_type = column("mime_type")
    assert isinstance(mime_type.type, String)
    assert mime_type.type.length == 100
    for name in ("file_path", "file_extension", "file_size_bytes", "mime_type"):
        assert column(name).nullable is True, name
        assert column(name).server_default is None, name


def test_created_at_is_a_required_timezone_aware_timestamp() -> None:
    created_at = column("created_at")
    assert isinstance(created_at.type, DateTime)
    assert created_at.type.timezone is True
    assert created_at.nullable is False
    assert "CURRENT_TIMESTAMP" in default_sql("created_at")


def test_supported_extensions_are_the_twelve_of_the_specification() -> None:
    assert SUPPORTED_EXTENSIONS == (
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".html",
        ".css",
        ".java",
        ".cpp",
        ".c",
        ".txt",
        ".md",
    )


def test_check_constraint_keeps_the_migration_name_and_lists_every_extension() -> None:
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert set(checks) == {"supported_extension"}
    for extension in SUPPORTED_EXTENSIONS:
        assert f"'{extension}'" in checks["supported_extension"]


def test_indexes_match_the_migration() -> None:
    indexes = {index.name: [c.name for c in index.columns] for index in TABLE.indexes}
    assert indexes == {"idx_code_files_uploaded_code_id": ["uploaded_code_id"]}


def test_there_is_no_unique_constraint() -> None:
    # An upload holds many files, and different folders may hold files with the same name.
    assert not any(c.__class__.__name__ == "UniqueConstraint" for c in TABLE.constraints)


def test_repr_shows_ids_but_not_the_file_names_or_paths() -> None:
    code_file = CodeFile(
        id=uuid.UUID(int=3),
        uploaded_code_id=uuid.UUID(int=9),
        file_name="비밀.py",
        storage_path="/비밀/경로",
    )
    text = repr(code_file)
    assert str(uuid.UUID(int=3)) in text
    assert str(uuid.UUID(int=9)) in text
    assert "비밀" not in text


def test_uploaded_code_has_many_files_and_a_file_belongs_to_one_upload() -> None:
    upload_side = class_mapper(UploadedCode).relationships["code_files"]
    file_side = class_mapper(CodeFile).relationships["uploaded_code"]
    assert upload_side.mapper.class_ is CodeFile
    assert file_side.mapper.class_ is UploadedCode
    assert upload_side.back_populates == "uploaded_code"
    assert file_side.back_populates == "code_files"
    assert upload_side.uselist is True
    assert file_side.uselist is False


def test_deleting_an_upload_deletes_its_files_and_leaves_that_to_the_database() -> None:
    upload_side = class_mapper(UploadedCode).relationships["code_files"]
    assert upload_side.cascade.delete is True
    assert upload_side.cascade.delete_orphan is True
    assert upload_side.passive_deletes is True


def test_relationships_never_lazy_load() -> None:
    assert class_mapper(UploadedCode).relationships["code_files"].lazy == "raise"
    assert class_mapper(CodeFile).relationships["uploaded_code"].lazy == "raise"
