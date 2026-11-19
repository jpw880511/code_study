import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Engine, Table, func, inspect, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models import CodeFile, Project, Task, UploadedCode, User
from src.models.code_file import SUPPORTED_EXTENSIONS


async def saved_upload(session: AsyncSession, number: int = 1) -> UploadedCode:
    user = User(email=f"{uuid.uuid4().hex}@example.com", password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, title="프로젝트")
    session.add(project)
    await session.flush()
    task = Task(project_id=project.id, task_number=number, title="첫 번째 작업")
    session.add(task)
    await session.flush()
    upload = UploadedCode(task_id=task.id)
    session.add(upload)
    await session.flush()
    return upload


def new_file(upload: UploadedCode, name: str = "main.py", **values: object) -> CodeFile:
    values.setdefault("storage_path", f"storage/uploads/{uuid.uuid4()}.py")
    return CodeFile(uploaded_code_id=upload.id, file_name=name, **values)


async def count_files(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(CodeFile))).scalar_one()


async def test_database_fills_in_the_defaults(session: AsyncSession) -> None:
    code_file = new_file(await saved_upload(session))
    session.add(code_file)
    await session.flush()

    # No refresh(): the values must already be loaded (async sessions cannot lazy-load).
    assert code_file.id is not None
    for value in (
        code_file.file_path,
        code_file.file_extension,
        code_file.file_size_bytes,
        code_file.mime_type,
    ):
        assert value is None
    assert code_file.created_at.tzinfo is not None
    assert abs(code_file.created_at - datetime.now(UTC)) < timedelta(minutes=1)


async def test_every_field_round_trips(session: AsyncSession) -> None:
    session.add(
        new_file(
            await saved_upload(session),
            "util.py",
            file_path="src/lib/util.py",
            file_extension=".py",
            file_size_bytes=2048,
            storage_path="storage/uploads/u/t/abc.py",
            mime_type="text/x-python",
        )
    )
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(CodeFile))).scalar_one()
    assert stored.file_name == "util.py"
    assert stored.file_path == "src/lib/util.py"
    assert stored.file_extension == ".py"
    assert stored.file_size_bytes == 2048
    assert stored.storage_path == "storage/uploads/u/t/abc.py"
    assert stored.mime_type == "text/x-python"


@pytest.mark.parametrize("extension", SUPPORTED_EXTENSIONS)
async def test_every_supported_extension_is_accepted(session: AsyncSession, extension: str) -> None:
    code_file = new_file(await saved_upload(session), file_extension=extension)
    session.add(code_file)
    await session.flush()
    assert code_file.file_extension == extension


@pytest.mark.parametrize("extension", [".exe", ".PY", "py", ".pyc", ".zip", ""])
async def test_other_extensions_are_rejected(session: AsyncSession, extension: str) -> None:
    session.add(new_file(await saved_upload(session), file_extension=extension))
    with pytest.raises(IntegrityError, match="supported_extension"):
        await session.flush()


async def test_a_file_without_an_extension_value_is_allowed(session: AsyncSession) -> None:
    # SQL CHECK constraints pass on NULL; the upload validator (T064) decides what to accept.
    session.add(new_file(await saved_upload(session), file_extension=None))
    await session.flush()
    assert await count_files(session) == 1


async def test_file_name_and_storage_path_are_required(session: AsyncSession) -> None:
    upload = await saved_upload(session)
    session.add(CodeFile(uploaded_code_id=upload.id, storage_path="x"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    upload = await saved_upload(session, 2)
    session.add(CodeFile(uploaded_code_id=upload.id, file_name="a.py"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_file_name_is_limited_to_255_characters(session: AsyncSession) -> None:
    upload = await saved_upload(session)
    session.add(new_file(upload, "a" * 255))
    await session.flush()
    session.add(new_file(upload, "a" * 256))
    with pytest.raises(Exception, match="value too long"):
        await session.flush()


async def test_uploaded_code_id_is_required(session: AsyncSession) -> None:
    session.add(CodeFile(file_name="a.py", storage_path="x"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_file_must_belong_to_an_existing_upload(session: AsyncSession) -> None:
    session.add(CodeFile(uploaded_code_id=uuid.uuid4(), file_name="a.py", storage_path="x"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_an_upload_can_hold_many_files_even_with_the_same_name(
    session: AsyncSession,
) -> None:
    upload = await saved_upload(session)
    session.add_all(
        [
            new_file(upload, "index.js", file_path="a/index.js"),
            new_file(upload, "index.js", file_path="b/index.js"),
            new_file(upload, "style.css"),
        ]
    )
    await session.flush()
    assert await count_files(session) == 3


async def test_upload_loads_its_files_and_a_file_loads_its_upload(session: AsyncSession) -> None:
    upload = await saved_upload(session)
    other = await saved_upload(session, 2)
    session.add_all([new_file(upload, "a.py"), new_file(upload, "b.py"), new_file(other, "c.py")])
    await session.flush()
    session.expunge_all()

    loaded = (
        await session.execute(
            select(UploadedCode)
            .where(UploadedCode.id == upload.id)
            .options(selectinload(UploadedCode.code_files))
        )
    ).scalar_one()
    assert sorted(f.file_name for f in loaded.code_files) == ["a.py", "b.py"]

    session.expunge_all()
    code_file = (
        await session.execute(
            select(CodeFile)
            .where(CodeFile.file_name == "c.py")
            .options(selectinload(CodeFile.uploaded_code))
        )
    ).scalar_one()
    assert code_file.uploaded_code.id == other.id


async def test_relationships_must_be_loaded_explicitly_in_async_code(session: AsyncSession) -> None:
    session.add(new_file(await saved_upload(session)))
    await session.flush()
    session.expunge_all()

    stored = (await session.execute(select(UploadedCode))).scalar_one()

    with pytest.raises(InvalidRequestError):
        _ = stored.code_files


async def test_deleting_an_upload_deletes_its_files(session: AsyncSession) -> None:
    upload = await saved_upload(session)
    other = await saved_upload(session, 2)
    session.add_all([new_file(upload, "a.py"), new_file(upload, "b.py"), new_file(other, "c.py")])
    await session.flush()
    session.expunge_all()
    loaded = (
        await session.execute(
            select(UploadedCode)
            .where(UploadedCode.id == upload.id)
            .options(selectinload(UploadedCode.code_files))
        )
    ).scalar_one()

    await session.delete(loaded)
    await session.flush()

    assert (await session.execute(select(CodeFile.file_name))).scalars().all() == ["c.py"]


async def test_deleting_a_project_deletes_the_files_of_its_tasks(session: AsyncSession) -> None:
    session.add(new_file(await saved_upload(session)))
    await session.flush()
    project = (await session.execute(select(Project))).scalar_one()

    await session.delete(project)
    await session.flush()

    assert await count_files(session) == 0


def test_model_matches_the_migrated_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table = cast(Table, CodeFile.__table__)

    db_columns = {c["name"]: c for c in inspector.get_columns("code_files")}
    assert set(db_columns) == set(table.c.keys())
    for model_column in table.c:
        db_column = db_columns[model_column.name]
        assert db_column["nullable"] == model_column.nullable, model_column.name
        db_length = getattr(db_column["type"], "length", None)
        assert db_length == getattr(model_column.type, "length", None), model_column.name

    assert str(db_columns["id"]["default"]).startswith("gen_random_uuid()")
    assert "CURRENT_TIMESTAMP" in str(db_columns["created_at"]["default"])
    for name in set(table.c.keys()) - {"id", "created_at"}:
        assert db_columns[name]["default"] is None, name

    assert inspector.get_pk_constraint("code_files")["constrained_columns"] == ["id"]

    (foreign_key,) = inspector.get_foreign_keys("code_files")
    assert foreign_key["constrained_columns"] == ["uploaded_code_id"]
    assert foreign_key["referred_table"] == "uploaded_code"
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    db_indexes = {i["name"]: i for i in inspector.get_indexes("code_files")}
    assert set(db_indexes) == {i.name for i in table.indexes}
    for index in table.indexes:
        assert db_indexes[index.name]["column_names"] == [c.name for c in index.columns]
    assert inspector.get_unique_constraints("code_files") == []

    db_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("code_files")}
    model_checks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
    assert model_checks == set(db_checks) == {"supported_extension"}
    for extension in SUPPORTED_EXTENSIONS:
        assert f"'{extension}'" in db_checks["supported_extension"]
