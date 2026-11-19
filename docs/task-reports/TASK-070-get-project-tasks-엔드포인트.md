# TASK-070. GET /projects/{project_id}/tasks 엔드포인트

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
프로젝트의 Task 목록을 돌려준다. `GET /api/v1/projects/{project_id}/tasks` → `200`, 본문은 `TaskResponse[]`(bare array).
- `task_number` 오름차순, 휴지통 Task 제외, 다른 프로젝트의 Task 제외.
- 각 항목에 `upload`(업로드 요약 또는 `null`)를 포함한다. `storage_path`, `user_id`, 삭제 관련 컬럼은 응답에 없다(응답 스키마를 필드별로 명시해 만든다).
- 프로젝트 규칙: 없는 프로젝트 404 `project_not_found`, 휴지통 프로젝트 404, 남의 프로젝트 403 `project_forbidden`, 로그인 없으면 401, 형식이 틀린 UUID는 422 `validation_error`.
- 이 작업에서 라우터(`api/tasks.py`, `tasks_router`)와 스키마(`api/task_schemas.py`), 라우터 등록(`api/router.py`), 서비스 오류 코드의 상태 매핑(`DOMAIN_ERROR_STATUS`)을 처음 만들었다.

## 변경 파일
- `backend/src/api/tasks.py`, `backend/src/api/task_schemas.py` (신규)
- `backend/src/api/router.py` (`tasks_router` 등록), `backend/src/api/exceptions.py` (상태 매핑)
- `backend/tests/integration/test_tasks_api_db.py` (신규; 전체 68개 중 이 작업 관련: 인증 표, 목록 4개)

## TDD 결과
- RED: `api/tasks.py`가 없어(그리고 `AppSettings`에 `upload_storage_path`가 없어) 테스트가 실패.
- GREEN: 통과. 순서·bare array·응답 키 집합 정확히 일치·내부 키 미노출·휴지통 제외·빈 목록 `[]`·프로젝트 403/404/휴지통 404.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 서비스는 항상 `selectinload`로 업로드 요약을 함께 읽어 N+1 쿼리를 피한다.
- 응답 객체는 `_task_fields()`로 모델에서 필드를 하나씩 꺼내 만든다. 모델에 컬럼이 추가돼도 응답에 새지 않는다.

## 비고
- 페이지네이션은 계약에 없어 넣지 않았다.
