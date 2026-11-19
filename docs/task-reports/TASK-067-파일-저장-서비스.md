# TASK-067. 파일 저장 서비스

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
업로드된 코드를 디스크에 저장하고 다시 읽는 서비스(`FileStorage`)를 만들었다. 저장 위치는 `{저장 루트}/{user_id}/{task_id}/{uuid4}{확장자}`이고, DB에는 저장 루트 기준 상대 경로(`/` 구분)만 남긴다.
- `save(user_id, task_id, extension, content)`: 지원 확장자 12개 중 하나일 때만 저장하고 상대 경로를 돌려준다.
- `read(storage_path)`: 경로를 해석한 결과가 저장 루트 밖이면 읽지 않고 `CodeFileMissingError`(404 `code_file_missing`)로 거부한다. 없는 파일과 디렉터리도 같은 오류다.
- `discard_task(user_id, task_id)`: Task 폴더를 지우고, 사용자 폴더가 비면 그것도 지운다(원자성 복구용).
- 저장 루트 설정 `UPLOAD_STORAGE_PATH`(`AppSettings.upload_storage_path`)를 추가했다. 기본값은 저장소 루트의 `storage/uploads`, 상대 경로는 저장소 루트 기준으로 해석한다. `.env.example`에 키를 추가했다.
- API가 쓰는 의존성 `get_file_storage` / `Storage`를 `api/dependencies.py`에 추가했다.

## 변경 파일
- `backend/src/services/code_analysis/file_storage.py` (신규)
- `backend/src/config.py` (`upload_storage_path`)
- `backend/src/api/dependencies.py` (`get_file_storage`, `Storage`)
- `.env.example` (`UPLOAD_STORAGE_PATH`)
- `backend/tests/unit/test_file_storage.py` (신규, 31개), `backend/tests/unit/test_upload_config_and_errors.py` (설정 부분)

## TDD 결과
- RED: `file_storage` 모듈이 없어 수집 단계에서 `ModuleNotFoundError`.
- GREEN: 신규 31개 + 설정 4개 통과.
- 경로 탈출 테스트: `..`, 절대 경로(POSIX·Windows 드라이브), 역슬래시, 빈 세그먼트, `.`, NUL, 저장 루트 밖을 가리키는 절대 경로, **루트 밖으로 나가는 링크**(심볼릭 링크 권한이 없는 Windows에서는 디렉터리 정션으로 대체)를 모두 거부하고, 루트 안을 가리키는 링크는 허용함을 확인.
- 전체: 통과, skip 0, 커버리지 100%, `ruff check`/`mypy src` 통과.

## 기술 결정
- 디스크 경로에는 서버가 만든 UUID와 검증된 확장자만 쓴다. 사용자가 입력한 파일명·상대 경로는 DB에만 들어간다.
- 읽을 때는 문자열 검사(`..`, 절대 경로, `:` 등)와 `resolve()` 후 `is_relative_to(root)` 검사를 모두 한다. 링크는 문자열 검사로는 못 잡으므로 resolve 검사가 필요하다.
- 경로 거부와 파일 없음은 같은 `code_file_missing`이다(DB 값은 서버가 만든 것이라, 밖을 가리키면 손상으로 보고 내용을 드러내지 않는다). 거부할 때는 경고 로그를 남긴다.
- 파일 I/O는 동기 코드이고, 서비스(T069)에서 `asyncio.to_thread`로 호출해 이벤트 루프를 막지 않는다.

## 비고
- 영구 삭제(30일 후)는 Phase 10 범위라 `discard_task`는 업로드 실패 복구에만 쓴다.
- DB 커밋이 응답 직전에 실패하는 경우(`get_session`의 커밋 단계)에는 이미 쓴 파일이 남을 수 있다. 서비스 안의 실패는 savepoint와 파일 삭제로 되돌리지만 커밋 실패는 서비스 밖이다. 고아 파일 정리는 후속 과제다.
