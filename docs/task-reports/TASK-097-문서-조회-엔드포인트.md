# TASK-097: GET /tasks/{task_id}/document

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
Task의 학습 문서를 돌려준다(`api/documents.py`, `api/document_schemas.py`). 계약대로 `task_id`, `status`, `content`, `generation_started_at`, `generation_completed_at`, `error`, `created_at`, `updated_at`만 담는다.
- `content`는 `completed`일 때만 7개 챕터, 그 밖에는 `null`(자리표시자 챕터를 내보내지 않음). `error`는 `failed`일 때만.
- `celery_task_id`, `storage_path` 등 내부 컬럼은 응답 스키마를 필드별로 만들어 새지 않는다(테스트로 확인).
- 소유권·휴지통 규칙은 `TaskService.get` 한 곳을 재사용: 401 `not_authenticated`, 403 `task_forbidden`, 404 `task_not_found`(휴지통 Task/프로젝트 포함), 문서 행이 없으면 404 `document_not_found`("이 Task에는 아직 학습 문서가 없습니다."). `DOMAIN_ERROR_STATUS`에 `document_not_found: 404` 추가.
- 15분 넘은 `in_progress`는 읽을 때 `failed`로 바뀐다.

## 변경 파일
- `backend/src/api/documents.py`, `backend/src/api/document_schemas.py` (신규), `backend/src/api/router.py`, `backend/src/api/exceptions.py`
- `backend/tests/integration/test_documents_api_db.py` (신규, 28개 중 문서 엔드포인트 관련)
- `backend/tests/unit/test_domain_errors.py`: `DOMAIN_ERROR_STATUS`를 통째로 비교하는 기존 단언에 새 항목 `document_not_found: 404`를 추가했다(단언을 약화한 것이 아니라 새 오류 코드를 반영한 변경).

## TDD 결과
- RED: 엔드포인트와 모듈이 없어 실패.
- GREEN: 401/403/404(없는 Task, 휴지통 Task, 휴지통 프로젝트), 잘못된 UUID 422, 문서 없음 404, `pending`/`in_progress`/`failed`에서 `content` null, `completed`에서 7챕터 그대로, 응답 키 집합 고정, 내부 값 미노출, 오래된 `in_progress`가 `failed`로.

## 기술 결정
- 상태 엔드포인트와 같은 `DocumentQueueService.get`을 써서 두 엔드포인트의 응답이 일치한다.

## 비고
- 계약과 다르게 한 점은 없다.
