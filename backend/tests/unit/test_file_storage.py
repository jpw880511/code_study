import os
import subprocess
import uuid
from pathlib import Path

import pytest
from src.services.code_analysis.file_storage import FileStorage
from src.services.task_errors import CodeFileMissingError

USER = uuid.uuid4()
TASK = uuid.uuid4()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def storage(root: Path) -> FileStorage:
    return FileStorage(root)


def files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


def test_save_writes_under_user_and_task_folders_and_returns_a_relative_path(
    storage: FileStorage, root: Path
) -> None:
    stored = storage.save(USER, TASK, ".py", b"print(1)\n")

    assert stored.startswith(f"{USER}/{TASK}/")
    assert stored.endswith(".py")
    assert "\\" not in stored
    assert (root / stored).read_bytes() == b"print(1)\n"


def test_the_file_name_is_a_server_made_uuid(storage: FileStorage) -> None:
    stored = storage.save(USER, TASK, ".jsx", b"x")

    name = stored.rsplit("/", 1)[1]
    assert name.endswith(".jsx")
    uuid.UUID(name[: -len(".jsx")])


def test_two_saves_never_share_a_path(storage: FileStorage) -> None:
    assert storage.save(USER, TASK, ".py", b"a") != storage.save(USER, TASK, ".py", b"b")


@pytest.mark.parametrize("extension", [".exe", "", "py", ".py/../x", "/.py", ".PY", ".py "])
def test_save_refuses_an_extension_outside_the_supported_list(
    storage: FileStorage, root: Path, extension: str
) -> None:
    with pytest.raises(ValueError, match="extension"):
        storage.save(USER, TASK, extension, b"x")
    assert files_under(root) == []


def test_read_returns_what_was_saved(storage: FileStorage) -> None:
    stored = storage.save(USER, TASK, ".md", "# 제목".encode())

    assert storage.read(stored) == "# 제목".encode()


def test_reading_a_missing_file_is_code_file_missing(storage: FileStorage) -> None:
    with pytest.raises(CodeFileMissingError):
        storage.read(f"{USER}/{TASK}/{uuid.uuid4()}.py")


def test_reading_a_directory_is_code_file_missing(storage: FileStorage, root: Path) -> None:
    (root / "folder").mkdir(parents=True)

    with pytest.raises(CodeFileMissingError):
        storage.read("folder")


@pytest.mark.parametrize(
    "bad_path",
    [
        "../secret.py",
        "a/../../secret.py",
        "a/../b.py",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "C:\\Windows\\win.ini",
        "a\\b.py",
        "..\\secret.py",
        "a//b.py",
        "./a.py",
        "",
        "a\x00b.py",
    ],
)
def test_reading_outside_the_storage_root_is_refused(
    storage: FileStorage, root: Path, bad_path: str
) -> None:
    (root.parent / "secret.py").write_text("secret")
    (root / "ok").mkdir(parents=True)

    with pytest.raises(CodeFileMissingError):
        storage.read(bad_path)


def test_an_absolute_path_to_a_real_file_is_refused(storage: FileStorage, tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("x")

    with pytest.raises(CodeFileMissingError):
        storage.read(str(outside))
    with pytest.raises(CodeFileMissingError):
        storage.read(outside.as_posix())


def link_directory(link: Path, target: Path) -> None:
    """A symlink, or on Windows without the privilege a junction (the same escape route)."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True
        )


def test_a_link_that_leads_out_of_the_root_is_refused(
    storage: FileStorage, root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret")
    root.mkdir()
    link_directory(root / "link", outside)

    with pytest.raises(CodeFileMissingError):
        storage.read("link/secret.py")


def test_a_link_that_stays_inside_the_root_still_works(storage: FileStorage, root: Path) -> None:
    stored = storage.save(USER, TASK, ".py", b"ok")
    link_directory(root / "alias", root / str(USER))

    assert storage.read(f"alias/{stored.split('/', 1)[1]}") == b"ok"


def test_discard_removes_the_task_folder_and_the_empty_user_folder(
    storage: FileStorage, root: Path
) -> None:
    storage.save(USER, TASK, ".py", b"a")
    storage.save(USER, TASK, ".js", b"b")

    storage.discard_task(USER, TASK)

    assert not (root / str(USER) / str(TASK)).exists()
    assert not (root / str(USER)).exists()
    assert root.exists()


def test_discard_keeps_other_tasks_of_the_same_user(storage: FileStorage, root: Path) -> None:
    other_task = uuid.uuid4()
    keep = storage.save(USER, other_task, ".py", b"keep")
    storage.save(USER, TASK, ".py", b"drop")

    storage.discard_task(USER, TASK)

    assert (root / keep).read_bytes() == b"keep"
    assert not (root / str(USER) / str(TASK)).exists()


def test_discard_without_anything_saved_is_a_no_op(storage: FileStorage) -> None:
    storage.discard_task(USER, TASK)
