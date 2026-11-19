# TASK-071. POST /projects/{project_id}/tasks 엔드포인트 (multipart 업로드)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
Task와 업로드 코드를 한 번에 만든다. `POST /api/v1/projects/{project_id}/tasks`, `multipart/form-data` → `201 CreateTaskResponse`(TaskDetailResponse + `excluded_paths` + `warnings`).
- 필드: `title`, `upload_method`(필수), `description`, `files`(반복), `paths`(반복), `code`, `language`. 로직은 모두 `CodeUploadService`(TASK-069)가 하고 엔드포인트는 얇다.
- 오류: 계약의 코드·메시지 표 전체를 테스트로 검증한다(422 `invalid_upload_method`/`invalid_task_title`/`invalid_task_description`/`no_files`/`too_many_files`/`invalid_file_path`/`language_required`/`unsupported_language`/`empty_code`). `FileValidationError`는 `api/exceptions.py`의 새 핸들러가 `file_too_large`→413, `unsupported_file_type`/`binary_file_rejected`→415로 옮기며 `details`와 `suggestion`을 그대로 보존한다.
- 제목/설명 규칙은 서비스에서 검사한다(Pydantic이 아니라). `title`/`upload_method` 필드 자체가 없으면 기존대로 422 `validation_error`.
- 실패하면 DB·디스크 모두 원상태(API 수준에서도 행·파일·폴더 없음을 확인).
- 성공 시 `last_activity_at` 갱신, `task_number` 1부터 순차.

## 변경 파일
- `backend/src/api/tasks.py` (`create_task`, `LargeFieldRoute`), `backend/src/api/task_schemas.py`
- `backend/src/api/exceptions.py` (`handle_file_validation_error`, `FILE_VALIDATION_STATUS`)
- `backend/tests/integration/test_tasks_api_db.py` (생성 성공·오류 표 22건·세부 정보·프로젝트 규칙)
- `backend/tests/integration/test_tasks_api_commit_db.py` (신규 4개: 실제 `get_session` 커밋 확인)
- `backend/tests/unit/test_upload_config_and_errors.py` (신규 9개: 설정, 핸들러)

## TDD 결과
- RED: 엔드포인트 없음(404/수집 실패).
- GREEN: 통과. 확인한 것: 붙여넣기·파일·폴더 3방식의 성공 응답과 디스크 파일 수, 폴더 제외 목록, `large_code` 경고, **11MB 파일 → 413 `file_too_large`**(`details.max_size_mb`, `suggestion` 포함), 합계 초과 413, `.exe` 415(`details.extension`), 위장 바이너리 415, 경로 탈출/절대/역슬래시 422, 모든 파일이 제외되면 422 `no_files`, 남의 프로젝트는 잘못된 폼이어도 403, 휴지통·없는 프로젝트 404, 인증 없으면 401(본문을 읽은 뒤 의존성에서 거부).
- **실제 커밋**: 다른 세션이 Task·UploadedCode·CodeFile 행을 읽고, 디스크 파일 내용이 일치함. 거절된 업로드는 아무것도 커밋하지 않음.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- **큰 붙여넣기**: Starlette는 텍스트 필드를 1MB로 제한한다(초과 시 400 `bad_request`). 붙여넣기도 파일처럼 10MB까지 허용해야 하므로 이 라우트만 `LargeFieldRoute`로 폼을 먼저 `max_part_size=2×10MB`로 파싱해 둔다(FastAPI는 캐시된 폼을 그대로 쓴다). 2.4MB 붙여넣기는 201, 11.4MB 붙여넣기는 서비스의 413 `file_too_large`로 응답한다.
- 업로드 파트는 `IncomingFile`로 서비스에 넘기고 서비스가 파일당 `MAX+1`바이트까지만 읽는다.

## 비고
- 한계: 폼은 인증 의존성보다 먼저 파싱되므로 로그인 없는 요청도 본문(최대 약 20MB 필드, 최대 1000개 파일 파트)을 받은 뒤에 401이 나간다. 앞단(리버스 프록시)의 본문 크기 제한이나 속도 제한이 후속으로 필요하다.
- 한계: 필드 20MB를 넘는 붙여넣기는 413이 아니라 파서의 400 `bad_request`가 된다.
- 한계: 응답 직전 DB 커밋이 실패하면 쓴 파일이 남을 수 있다(TASK-067 비고).
