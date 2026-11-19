import io
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import CodeFile, Project, Task, UploadedCode, User
from src.models.uploaded_code import MAX_UPLOAD_SIZE_BYTES
from src.services.code_analysis.code_upload_service import (
    LARGE_CODE_WARNING,
    CodeUploadService,
    IncomingFile,
)
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.upload_errors import (
    EmptyCodeError,
    InvalidFilePathError,
    InvalidUploadMethodError,
    LanguageRequiredError,
    NoFilesError,
    TooManyFilesError,
    UnsupportedLanguageError,
)
from src.services.errors import DomainError
from src.services.project_errors import ProjectForbiddenError, ProjectNotFoundError
from src.services.project_service import ProjectService
from src.services.task_errors import (
    CodeFileMissingError,
    CodeNotFoundError,
    InvalidTaskDescriptionError,
    InvalidTaskTitleError,
    TaskForbiddenError,
    TaskNotFoundError,
)
from src.services.task_service import TaskService
from src.utils.file_validator import FileValidationError

TITLE = "계산기 함수 학습"
OLD = datetime(2020, 1, 1, tzinfo=UTC)


class Source:
    """An upload part that remembers how much the service asked it to read."""

    def __init__(self, content: bytes) -> None:
        self._buffer = io.BytesIO(content)
        self.requested: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.requested.append(size)
        return self._buffer.read(size)


def incoming(name: str, content: bytes | str) -> IncomingFile:
    data = content.encode() if isinstance(content, str) else content
    return IncomingFile(name=name, source=Source(data))


def files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def service(session: AsyncSession, root: Path) -> CodeUploadService:
    return CodeUploadService(session, FileStorage(root))


async def saved_user(session: AsyncSession, email: str = "student@example.com") -> User:
    user = User(email=email, password_hash="$2b$12$hash")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await saved_user(session)


@pytest.fixture
async def project(session: AsyncSession, user: User) -> Project:
    created = await ProjectService(session).create(user.id, "프로젝트")
    await session.execute(
        update(Project).where(Project.id == created.id).values(last_activity_at=OLD)
    )
    session.expunge_all()
    return created


async def count(session: AsyncSession, model: type) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def nothing_stored(session: AsyncSession, root: Path, project_id: uuid.UUID) -> None:
    """No rows, no files, no folders, and the project's activity untouched."""
    for model in (Task, UploadedCode, CodeFile):
        assert await count(session, model) == 0, model
    assert not root.exists() or list(root.rglob("*")) == []
    activity = (
        await session.execute(select(Project.last_activity_at).where(Project.id == project_id))
    ).scalar_one()
    assert activity == OLD


async def make(service: CodeUploadService, user: User, project: Project, **overrides: Any) -> Any:
    options: dict[str, Any] = {
        "title": TITLE,
        "description": None,
        "upload_method": "paste",
        "code": "print(1)\n",
        "language": "python",
    }
    options.update(overrides)
    return await service.create_task(user.id, project.id, **options)


# --- paste ---------------------------------------------------------------------------------


async def test_paste_creates_the_task_one_file_and_the_analysis(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    result = await make(service, user, project, description="  설명  ")

    task = result.task
    assert (task.task_number, task.title, task.description, task.upload_method) == (
        1,
        TITLE,
        "설명",
        "paste",
    )
    upload = task.uploaded_code
    assert upload is not None
    assert (upload.detected_language, upload.complexity_level) == ("python", "beginner")
    assert (upload.total_lines, upload.total_files, upload.upload_size_bytes) == (1, 1, 9)
    [code_file] = upload.code_files
    assert code_file.file_name == "pasted_code.py"
    assert code_file.file_path is None
    assert code_file.file_extension == ".py"
    assert code_file.file_size_bytes == 9
    assert code_file.mime_type == "text/x-python"
    assert code_file.storage_path.startswith(f"{user.id}/{task.id}/")
    assert code_file.storage_path.endswith(".py")
    assert (root / code_file.storage_path).read_bytes() == b"print(1)\n"
    assert result.excluded_paths == []
    assert result.warnings == []


@pytest.mark.parametrize(
    ("language", "extension", "detected"),
    [
        ("python", ".py", "python"),
        ("javascript", ".js", "javascript"),
        ("typescript", ".ts", "typescript"),
        ("java", ".java", "java"),
        ("c", ".c", "c"),
        ("cpp", ".cpp", "cpp"),
        ("html", ".html", "html"),
        ("css", ".css", "css"),
        ("markdown", ".md", "markdown"),
        ("text", ".txt", "text"),
        (" PYTHON ", ".py", "python"),
    ],
)
async def test_paste_names_the_file_after_the_chosen_language(
    service: CodeUploadService,
    user: User,
    project: Project,
    language: str,
    extension: str,
    detected: str,
) -> None:
    result = await make(service, user, project, language=language)

    [code_file] = result.task.uploaded_code.code_files
    assert code_file.file_name == f"pasted_code{extension}"
    assert code_file.file_extension == extension
    assert result.task.uploaded_code.detected_language == detected


async def test_paste_keeps_the_code_exactly_as_typed(
    root: Path, service: CodeUploadService, user: User, project: Project
) -> None:
    code = "\n  # 한글 주석\nprint('안녕')  \n\n"

    result = await make(service, user, project, code=code)

    [code_file] = result.task.uploaded_code.code_files
    assert (root / code_file.storage_path).read_bytes() == code.encode()
    assert code_file.file_size_bytes == len(code.encode())


@pytest.mark.parametrize("language", [None, "", "   "])
async def test_paste_needs_a_language(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    language: str | None,
) -> None:
    with pytest.raises(LanguageRequiredError) as raised:
        await make(service, user, project, language=language)
    assert raised.value.message == "업로드하기 전에 프로그래밍 언어를 선택하세요."
    await nothing_stored(session, root, project.id)


@pytest.mark.parametrize("language", ["rust", "py", "c++", "jsx", "bash", "../x"])
async def test_paste_refuses_a_language_outside_the_dropdown(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    language: str,
) -> None:
    with pytest.raises(UnsupportedLanguageError) as raised:
        await make(service, user, project, language=language)
    assert raised.value.message == "지원하지 않는 프로그래밍 언어입니다."
    await nothing_stored(session, root, project.id)


@pytest.mark.parametrize("code", [None, "", "  \n\t \n"])
async def test_paste_refuses_empty_code(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    code: str | None,
) -> None:
    with pytest.raises(EmptyCodeError) as raised:
        await make(service, user, project, code=code)
    assert raised.value.message == "붙여넣은 코드가 비어 있습니다."
    await nothing_stored(session, root, project.id)


async def test_paste_applies_the_file_checks(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(FileValidationError) as binary:
        await make(service, user, project, code="a\x00b")
    assert binary.value.code == "binary_file_rejected"

    with pytest.raises(FileValidationError) as large:
        await make(service, user, project, code="a" * (MAX_UPLOAD_SIZE_BYTES + 1))
    assert large.value.code == "file_too_large"

    await nothing_stored(session, root, project.id)


# --- file ----------------------------------------------------------------------------------


async def test_file_upload_stores_each_file_under_a_server_made_name(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    result = await make(
        service,
        user,
        project,
        upload_method="file",
        code=None,
        language=None,
        files=[incoming("main.py", "print(1)\n"), incoming("App.JSX", "export {}\n")],
    )

    upload = result.task.uploaded_code
    assert (upload.total_files, upload.upload_size_bytes) == (2, 9 + 10)
    by_name = {f.file_name: f for f in upload.code_files}
    assert set(by_name) == {"main.py", "App.JSX"}
    assert by_name["App.JSX"].file_extension == ".jsx"
    assert by_name["App.JSX"].file_path is None
    assert by_name["App.JSX"].mime_type == "text/javascript"
    for code_file in by_name.values():
        assert "main" not in code_file.storage_path.rsplit("/", 1)[1]
        assert "App" not in code_file.storage_path.rsplit("/", 1)[1]
    assert len(files_under(root)) == 2


async def test_file_upload_ignores_paths_and_keeps_only_the_base_name(
    service: CodeUploadService, user: User, project: Project
) -> None:
    result = await make(
        service,
        user,
        project,
        upload_method="file",
        files=[incoming("../../evil/dir\\main.py", "x = 1\n")],
        paths=["../../ignored/garbage", "/abs"],
    )

    [code_file] = result.task.uploaded_code.code_files
    assert (code_file.file_name, code_file.file_path) == ("main.py", None)


@pytest.mark.parametrize("name", ["", "dir/", "..", "a\x00.py", "x" * 256 + ".py"])
async def test_file_upload_refuses_an_unusable_file_name(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    name: str,
) -> None:
    with pytest.raises(InvalidFilePathError):
        await make(service, user, project, upload_method="file", files=[incoming(name, "x")])
    await nothing_stored(session, root, project.id)


async def test_file_upload_without_files_is_refused(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(NoFilesError) as raised:
        await make(service, user, project, upload_method="file", files=[])
    assert raised.value.message == "업로드할 파일을 선택하세요."
    await nothing_stored(session, root, project.id)


async def test_twenty_files_are_fine_and_twenty_one_are_not(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    too_many = [incoming(f"f{i}.py", "x = 1\n") for i in range(21)]
    with pytest.raises(TooManyFilesError) as raised:
        await make(service, user, project, upload_method="file", files=too_many)
    assert raised.value.message == (
        "업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요."
    )
    assert all(f.source.requested == [] for f in too_many)  # nothing was even read
    await nothing_stored(session, root, project.id)

    ok = [incoming(f"f{i}.py", "x = 1\n") for i in range(20)]
    result = await make(service, user, project, upload_method="file", files=ok)
    assert result.task.uploaded_code.total_files == 20


# --- folder --------------------------------------------------------------------------------


async def test_folder_upload_keeps_relative_paths_and_reports_excluded_ones(
    service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    files = [
        incoming("App.jsx", "export default 1\n"),
        incoming("config", "[core]\n"),
        incoming("index.js", "module.exports = 1\n"),
        incoming("x.pyc", b"\x00\x01binary"),
        incoming(".DS_Store", b"\x00\x00"),
        incoming("util.py", "def f():\n    return 1\n"),
    ]
    paths = [
        "my-app/src/App.jsx",
        "my-app/.git/config",
        "my-app/node_modules/a/index.js",
        "my-app/src/__pycache__/x.pyc",
        "my-app/.DS_Store",
        "my-app/util.py",
    ]

    result = await make(
        service, user, project, upload_method="folder", code=None, language=None,
        files=files, paths=paths,
    )  # fmt: skip

    assert result.excluded_paths == [
        "my-app/.git/config",
        "my-app/node_modules/a/index.js",
        "my-app/src/__pycache__/x.pyc",
        "my-app/.DS_Store",
    ]
    upload = result.task.uploaded_code
    by_path = {f.file_path: f for f in upload.code_files}
    assert set(by_path) == {"my-app/src/App.jsx", "my-app/util.py"}
    assert by_path["my-app/src/App.jsx"].file_name == "App.jsx"
    assert upload.total_files == 2
    assert len(files_under(root)) == 2
    for excluded in files[1:5]:
        assert excluded.source.requested == []  # excluded parts are never read


async def test_excluded_files_do_not_count_toward_the_limit_of_twenty(
    service: CodeUploadService, user: User, project: Project
) -> None:
    files = [incoming(f"f{i}.py", "x = 1\n") for i in range(15)]
    files += [incoming(f"m{i}.js", "x") for i in range(10)]
    paths = [f"app/f{i}.py" for i in range(15)] + [f"app/node_modules/m{i}.js" for i in range(10)]

    result = await make(service, user, project, upload_method="folder", files=files, paths=paths)

    assert result.task.uploaded_code.total_files == 15
    assert len(result.excluded_paths) == 10


async def test_a_folder_of_only_excluded_files_is_no_files(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(NoFilesError):
        await make(
            service,
            user,
            project,
            upload_method="folder",
            files=[incoming("config", "x")],
            paths=["app/.git/config"],
        )
    await nothing_stored(session, root, project.id)


async def test_folder_paths_must_match_the_files_one_to_one(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    for paths in ([], ["a/x.py"], ["a/x.py", "a/y.py", "a/z.py"]):
        with pytest.raises(InvalidFilePathError):
            await make(
                service,
                user,
                project,
                upload_method="folder",
                files=[incoming("x.py", "x"), incoming("y.py", "y")],
                paths=paths,
            )
    await nothing_stored(session, root, project.id)


@pytest.mark.parametrize(
    "bad_path", ["/etc/x.py", "../x.py", "a/../x.py", "a\\x.py", "a//x.py", "", "a/./x.py"]
)
async def test_folder_refuses_an_unsafe_path_even_when_it_would_be_excluded(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    bad_path: str,
) -> None:
    files = [incoming("x.py", "x = 1\n"), incoming("config", "x")]
    with pytest.raises(InvalidFilePathError):
        await make(
            service,
            user,
            project,
            upload_method="folder",
            files=files,
            paths=["app/x.py", bad_path or "app/.git/"],
        )
    await nothing_stored(session, root, project.id)


async def test_unsafe_user_paths_never_reach_the_disk_path(
    service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    result = await make(
        service,
        user,
        project,
        upload_method="folder",
        files=[incoming("x.py", "x = 1\n")],
        paths=["a b/한글 폴더/x.py"],
    )

    [path] = files_under(root)
    assert path.relative_to(root).parts[:2] == (str(user.id), str(result.task.id))
    assert path.name != "x.py" and path.suffix == ".py"
    assert "한글" not in str(path.relative_to(root))


# --- per-file checks, sizes ----------------------------------------------------------------


async def test_unsupported_extension_is_refused_and_nothing_is_stored(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(FileValidationError) as raised:
        await make(
            service,
            user,
            project,
            upload_method="file",
            files=[incoming("good.py", "x = 1\n"), incoming("tool.exe", "MZ")],
        )
    assert raised.value.code == "unsupported_file_type"
    assert raised.value.details["extension"] == ".exe"
    await nothing_stored(session, root, project.id)


async def test_binary_content_is_refused_and_nothing_is_stored(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(FileValidationError) as raised:
        await make(
            service,
            user,
            project,
            upload_method="file",
            files=[incoming("good.py", "x = 1\n"), incoming("fake.py", b"\x89PNG\r\n\x1a\n\x00")],
        )
    assert raised.value.code == "binary_file_rejected"
    await nothing_stored(session, root, project.id)


async def test_a_file_over_10mb_is_refused_after_reading_only_one_byte_too_many(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    huge = incoming("big.py", b"a" * (MAX_UPLOAD_SIZE_BYTES + 1_000_000))

    with pytest.raises(FileValidationError) as raised:
        await make(service, user, project, upload_method="file", files=[huge])

    assert raised.value.code == "file_too_large"
    assert raised.value.message == "파일 크기가 10MB를 초과합니다."
    assert huge.source.requested == [MAX_UPLOAD_SIZE_BYTES + 1]
    await nothing_stored(session, root, project.id)


async def test_exactly_10mb_is_accepted(
    service: CodeUploadService, user: User, project: Project
) -> None:
    content = (b"x = 1\n" * 2_000_000)[:MAX_UPLOAD_SIZE_BYTES]

    result = await make(
        service, user, project, upload_method="file", files=[incoming("big.py", content)]
    )

    assert result.task.uploaded_code.upload_size_bytes == MAX_UPLOAD_SIZE_BYTES


async def test_the_total_of_all_files_is_limited_to_10mb(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    half = b"x = 1\n" * 1_000_000  # 6 MB each
    with pytest.raises(FileValidationError) as raised:
        await make(
            service,
            user,
            project,
            upload_method="file",
            files=[incoming("a.py", half), incoming("b.py", half)],
        )
    assert raised.value.code == "file_too_large"
    assert raised.value.message == "업로드한 파일의 전체 크기가 10MB를 초과합니다."
    await nothing_stored(session, root, project.id)


# --- analysis ------------------------------------------------------------------------------


async def test_the_analysis_covers_all_files(
    service: CodeUploadService, user: User, project: Project
) -> None:
    python_source = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
    result = await make(
        service,
        user,
        project,
        upload_method="folder",
        files=[
            incoming("README.md", "# 제목\n\n" + "문서\n" * 40),
            incoming("main.py", python_source),
            incoming("util.js", "function f() {\n  return 1;\n}\n"),
        ],
        paths=["app/README.md", "app/main.py", "app/util.js"],
    )

    upload = result.task.uploaded_code
    assert upload.detected_language == "python"  # 4 lines, vs 3 of JavaScript; markdown ignored
    assert upload.total_lines == 41 + 4 + 3
    assert upload.total_files == 3
    assert upload.complexity_level == "beginner"
    assert upload.upload_size_bytes == sum(f.file_size_bytes for f in upload.code_files)


async def test_a_big_upload_is_rated_by_its_code(
    service: CodeUploadService, user: User, project: Project
) -> None:
    result = await make(service, user, project, code="x = 1\n" * 350)

    assert result.task.uploaded_code.complexity_level == "advanced"


async def test_more_than_500_code_lines_adds_the_large_code_warning(
    service: CodeUploadService, user: User, project: Project
) -> None:
    result = await make(service, user, project, code="x = 1\n" * 501)

    assert [(w.code, w.message) for w in result.warnings] == [("large_code", LARGE_CODE_WARNING)]
    assert LARGE_CODE_WARNING == (
        "큰 코드 파일이 감지되었습니다. 500줄을 넘는 코드는 문서 생성에 3~5분이 걸릴 수 있습니다. "
        "다른 화면으로 이동했다가 준비되면 다시 돌아와도 됩니다."
    )


async def test_exactly_500_code_lines_or_a_long_document_has_no_warning(
    service: CodeUploadService, user: User, project: Project
) -> None:
    exact = await make(service, user, project, code="x = 1\n" * 500)
    assert exact.warnings == []

    long_text = await make(service, user, project, code="말\n" * 900, language="text")
    assert long_text.warnings == []
    assert long_text.task.uploaded_code.total_lines == 900


# --- order of checks, ownership ------------------------------------------------------------


async def test_the_method_is_checked_before_the_title_and_the_title_before_the_description(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(InvalidUploadMethodError) as method:
        await make(
            service, user, project, upload_method="zip", title="짧음", description="가" * 501
        )
    assert method.value.message == (
        "업로드 방식이 올바르지 않습니다. file, folder, paste 중 하나를 선택하세요."
    )

    with pytest.raises(InvalidTaskTitleError):
        await make(service, user, project, title="짧음", description="가" * 501, language=None)

    with pytest.raises(InvalidTaskDescriptionError):
        await make(service, user, project, description="가" * 501, language=None)

    await nothing_stored(session, root, project.id)


@pytest.mark.parametrize("method", [None, "", "zip", "FILE", " paste"])
async def test_an_unknown_upload_method_is_refused(
    service: CodeUploadService, user: User, project: Project, method: str | None
) -> None:
    with pytest.raises(InvalidUploadMethodError):
        await make(service, user, project, upload_method=method)


async def test_files_are_checked_in_order_so_the_first_problem_is_reported(
    service: CodeUploadService, user: User, project: Project
) -> None:
    with pytest.raises(FileValidationError) as raised:
        await make(
            service,
            user,
            project,
            upload_method="file",
            files=[incoming("a.exe", "x"), incoming("b.py", b"\x00\x00")],
        )
    assert raised.value.code == "unsupported_file_type"


async def test_a_foreign_project_is_forbidden_before_anything_is_validated(
    session: AsyncSession, service: CodeUploadService, root: Path, project: Project
) -> None:
    stranger = await saved_user(session, "stranger@example.com")
    unread = incoming("x.py", "x")

    with pytest.raises(ProjectForbiddenError):
        await service.create_task(
            stranger.id,
            project.id,
            title="짧음",
            description=None,
            upload_method="file",
            files=[unread],
        )

    assert unread.source.requested == []
    await nothing_stored(session, root, project.id)


async def test_a_trashed_or_missing_project_is_not_found(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    await ProjectService(session).soft_delete(user.id, project.id)

    with pytest.raises(ProjectNotFoundError):
        await make(service, user, project)
    with pytest.raises(ProjectNotFoundError):
        await service.create_task(
            user.id,
            uuid.uuid4(),
            title=TITLE,
            description=None,
            upload_method="paste",
            code="x",
            language="python",
        )
    assert files_under(root) == []


async def test_creating_moves_the_project_activity_forward(
    session: AsyncSession, service: CodeUploadService, user: User, project: Project
) -> None:
    before = datetime.now(UTC)

    await make(service, user, project)

    activity = (
        await session.execute(select(Project.last_activity_at).where(Project.id == project.id))
    ).scalar_one()
    assert activity >= before


# --- atomicity -----------------------------------------------------------------------------


class FailingStorage(FileStorage):
    """Saves the first files, then fails like a full disk would."""

    def __init__(self, root: Path, fail_on_call: int) -> None:
        super().__init__(root)
        self.calls = 0
        self.fail_on_call = fail_on_call

    def save(self, user_id: uuid.UUID, task_id: uuid.UUID, extension: str, content: bytes) -> str:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise OSError("disk full")
        return super().save(user_id, task_id, extension, content)


async def test_a_disk_failure_halfway_leaves_no_files_no_folder_no_rows(
    session: AsyncSession, root: Path, user: User, project: Project
) -> None:
    storage = FailingStorage(root, fail_on_call=3)
    service = CodeUploadService(session, storage)

    with pytest.raises(OSError, match="disk full"):
        await make(
            service,
            user,
            project,
            upload_method="file",
            files=[incoming(f"f{i}.py", "x = 1\n") for i in range(4)],
        )

    assert storage.calls == 3
    await nothing_stored(session, root, project.id)


async def test_a_database_failure_after_the_files_are_written_removes_them(
    session: AsyncSession,
    service: CodeUploadService,
    root: Path,
    user: User,
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_flush = session.flush

    async def flush_fails_once_files_exist(*args: Any, **kwargs: Any) -> None:
        if files_under(root):
            raise RuntimeError("database went away")
        await real_flush(*args, **kwargs)

    monkeypatch.setattr(session, "flush", flush_fails_once_files_exist)

    with pytest.raises(RuntimeError, match="database went away"):
        await make(service, user, project)

    monkeypatch.undo()
    await nothing_stored(session, root, project.id)


async def test_after_a_failure_the_next_task_still_gets_number_one(
    session: AsyncSession, root: Path, user: User, project: Project
) -> None:
    with pytest.raises(OSError):
        await make(CodeUploadService(session, FailingStorage(root, 1)), user, project)

    result = await make(CodeUploadService(session, FileStorage(root)), user, project)

    assert result.task.task_number == 1


# --- read_code -----------------------------------------------------------------------------


async def test_read_code_returns_the_files_sorted_with_content_and_language(
    service: CodeUploadService, user: User, project: Project
) -> None:
    created = await make(
        service,
        user,
        project,
        upload_method="folder",
        files=[
            incoming("b.py", "print('b')\n"),
            incoming("a.js", "const a = 1;\n"),
            incoming("README.md", "# 안녕\n"),
        ],
        paths=["app/src/b.py", "app/a.js", "app/README.md"],
    )

    codes = await service.read_code(user.id, created.task.id)

    assert [c.file.file_path for c in codes] == ["app/README.md", "app/a.js", "app/src/b.py"]
    assert [c.language for c in codes] == ["markdown", "javascript", "python"]
    assert [c.content for c in codes] == ["# 안녕\n", "const a = 1;\n", "print('b')\n"]


async def test_read_code_orders_by_file_name_when_there_is_no_path(
    service: CodeUploadService, user: User, project: Project
) -> None:
    created = await make(
        service,
        user,
        project,
        upload_method="file",
        files=[incoming("z.py", "z"), incoming("a.py", "a"), incoming("m.py", "m")],
    )

    codes = await service.read_code(user.id, created.task.id)

    assert [c.file.file_name for c in codes] == ["a.py", "m.py", "z.py"]


async def test_read_code_replaces_invalid_utf8_bytes(
    service: CodeUploadService, user: User, project: Project
) -> None:
    created = await make(
        service,
        user,
        project,
        upload_method="file",
        files=[incoming("legacy.py", b"# \xb0\xa1\nprint(1)\n")],
    )

    [code] = await service.read_code(user.id, created.task.id)

    assert code.content == "# ��\nprint(1)\n"


async def test_read_code_of_a_task_without_an_upload_is_code_not_found(
    session: AsyncSession, service: CodeUploadService, user: User, project: Project
) -> None:
    task = await TaskService(session).create(user.id, project.id, TITLE)

    with pytest.raises(CodeNotFoundError):
        await service.read_code(user.id, task.id)


async def test_read_code_with_a_file_gone_from_disk_is_code_file_missing(
    service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    created = await make(
        service,
        user,
        project,
        upload_method="file",
        files=[incoming("a.py", "a"), incoming("b.py", "b")],
    )
    files_under(root)[0].unlink()

    with pytest.raises(CodeFileMissingError):
        await service.read_code(user.id, created.task.id)


async def test_read_code_refuses_a_stored_path_that_leaves_the_root(
    session: AsyncSession, service: CodeUploadService, user: User, project: Project
) -> None:
    created = await make(service, user, project)
    await session.execute(update(CodeFile).values(storage_path="../../etc/passwd"))
    session.expunge_all()

    with pytest.raises(CodeFileMissingError):
        await service.read_code(user.id, created.task.id)


async def test_read_code_follows_the_task_ownership_rules(
    session: AsyncSession, service: CodeUploadService, user: User, project: Project
) -> None:
    created = await make(service, user, project)
    stranger = await saved_user(session, "stranger@example.com")

    with pytest.raises(TaskForbiddenError):
        await service.read_code(stranger.id, created.task.id)
    with pytest.raises(TaskNotFoundError):
        await service.read_code(user.id, uuid.uuid4())

    await TaskService(session).soft_delete(user.id, created.task.id)
    for who in (user, stranger):
        with pytest.raises(TaskNotFoundError):
            await service.read_code(who.id, created.task.id)


async def test_soft_deleting_a_task_keeps_its_files_on_disk(
    session: AsyncSession, service: CodeUploadService, root: Path, user: User, project: Project
) -> None:
    created = await make(service, user, project)

    await TaskService(session).soft_delete(user.id, created.task.id)

    assert len(files_under(root)) == 1


def test_domain_errors_of_the_upload_are_all_domain_errors() -> None:
    for error in (
        InvalidUploadMethodError(),
        NoFilesError(),
        TooManyFilesError(),
        InvalidFilePathError(),
        LanguageRequiredError(),
        UnsupportedLanguageError(),
        EmptyCodeError(),
    ):
        assert isinstance(error, DomainError)
    assert [
        e.code
        for e in (
            InvalidUploadMethodError(),
            NoFilesError(),
            TooManyFilesError(),
            InvalidFilePathError(),
            LanguageRequiredError(),
            UnsupportedLanguageError(),
            EmptyCodeError(),
        )
    ] == [
        "invalid_upload_method",
        "no_files",
        "too_many_files",
        "invalid_file_path",
        "language_required",
        "unsupported_language",
        "empty_code",
    ]
