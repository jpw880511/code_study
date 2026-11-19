# TASK-072. GET /tasks/{task_id} 엔드포인트

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
Task 한 건을 파일 목록과 함께 돌려준다. `GET /api/v1/tasks/{task_id}` → `200 TaskDetailResponse`(TaskResponse + `files`).
- `files`는 `file_path`(없으면 `file_name`) 오름차순이며 각 항목은 `CodeFileSummary`(`id`, `file_name`, `file_path`, `file_extension`, `file_size_bytes`, `mime_type`)만 담는다. `storage_path`는 노출하지 않는다.
- 업로드가 없는 Task는 `upload: null`, `files: []`.
- 규칙: 없는 Task 404 `task_not_found`, 휴지통 Task와 휴지통 프로젝트의 Task는 누구에게나 404, 남의 Task 403 `task_forbidden`, 형식이 틀린 UUID 422, 로그인 없으면 401.

## 변경 파일
- `backend/src/api/tasks.py` (`get_task`), `backend/src/api/task_schemas.py` (`task_detail_response`)
- `backend/tests/integration/test_tasks_api_db.py` (상세·정렬·내부 키 미노출·403/404/422)

## TDD 결과
- RED: 라우트 없음.
- GREEN: 통과. 폴더 업로드 3개 파일이 `app/README.md`, `app/a/b.js`, `app/z.py` 순으로 정렬됨, 응답 키 집합이 계약과 정확히 일치, 업로드 없는 Task 응답, 남의 Task 403, 없는 Task 404, 잘못된 UUID 422.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 정렬은 DB 콜레이션에 따라 달라지지 않도록 파이썬에서 `file_path or file_name` 기준으로 한다(`sort_files`, 코드 조회와 같은 함수).

## 비고
- 정렬은 코드 포인트 순이라 대문자가 소문자보다 앞선다(`README.md` < `a.js`). 계약이 대소문자 처리를 정하지 않아 단순 순서를 택했다.
