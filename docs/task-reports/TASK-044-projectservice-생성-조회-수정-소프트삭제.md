# TASK-044. ProjectService (생성, 조회, 수정, 소프트 삭제)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
프로젝트에 관한 규칙을 한곳에 모은 서비스입니다. `backend/src/services/project_service.py`의 `ProjectService(session)`:
- **`create(user_id, title, description=None)`**: 제목/설명을 다듬어(양끝 공백 제거) 저장. 빈 설명은 NULL로 저장. `last_activity_at`은 생성 시각(DB 기본값).
- **`get(user_id, project_id)`**, **`list(user_id)`**: 본인의 **활성** 프로젝트만. 목록은 `last_activity_at` 내림차순, 같으면 `created_at` 내림차순(`last_activity_at`이 NULL이면 맨 뒤).
- **`update(user_id, project_id, *, title=UNSET, description=UNSET)`**: 넘긴 필드만 변경(`UNSET`은 "건드리지 않음", `None`은 "설명 지우기"). 제목이 `None`/공백이면 오류. `updated_at`만 갱신되고 `last_activity_at`은 그대로(그 값은 "마지막 Task 활동"이므로).
- **`soft_delete(user_id, project_id)`**: `deletion_status='trashed'`, `trashed_at`=지금(UTC), `scheduled_deletion_at`=30일 뒤.
- 검증 함수 `normalize_title`, `normalize_description`(모듈 수준, 단위 테스트 가능).
- 공통 오류 기반 클래스 `DomainError`(`backend/src/services/errors.py`)를 새로 만들고, `AuthError`를 그 하위 클래스로 바꿈(동작 변화 없음). 프로젝트 오류 4종(`backend/src/services/project_errors.py`): `project_not_found`, `project_forbidden`, `invalid_project_title`, `invalid_project_description`. 문구는 지시된 한국어 그대로.

## 변경 파일
- `backend/src/services/errors.py`, `backend/src/services/project_errors.py`, `backend/src/services/project_service.py` (신규)
- `backend/src/services/auth/errors.py` (`AuthError`가 `DomainError`를 상속)
- `backend/tests/unit/test_project_validation.py` (19개), `backend/tests/unit/test_domain_errors.py` (13개), `backend/tests/integration/test_project_service_db.py` (42개) (신규)

## TDD 결과
- RED: 테스트 먼저 작성 → `No module named 'src.services.project_errors'` 등으로 수집 단계 실패 확인
- GREEN: 구현 후 해당 테스트 전부 통과, 기존 `AuthError` 테스트도 그대로 통과
- REFACTOR: Black/Ruff/MyPy(strict) 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/services/project_service.py` 100%
- 검증 범위: 다듬기, 빈/공백/255·256자/NUL 문자 제목, 빈/2000·2001자 설명, 부분 수정, 명시적 `None` 설명, 아무것도 안 바꾸는 호출(`updated_at` 그대로), 같은 값으로 수정(변경 없음), 목록 필터/정렬/타이브레이커, 소프트 삭제 필드와 30일 정확히, 삭제 후 get/list에서 사라짐, SQL 주입/HTML 문자열이 그대로 저장됨

## 기술 결정
- **설명 2000자 상한은 우리가 정한 안전 한도**입니다. DB 열은 길이 제한이 없는 TEXT이고 요구사항 문서에도 값이 없습니다. 필요하면 `MAX_DESCRIPTION_LENGTH` 한 곳만 바꾸면 됩니다.
- **NUL 문자(`\x00`)는 거부.** PostgreSQL은 문자열에 NUL을 저장할 수 없어, 그대로 두면 500 오류가 납니다. 사용자의 입력 실수이므로 422(`invalid_project_title`/`invalid_project_description`)로 처리. 지시된 코드 목록을 늘리지 않으려고 새 오류 코드 없이 같은 코드에 별도 메시지를 사용.
- **`UNSET` 센티넬(Enum 하나).** `None`이 "지우기"라는 실제 값이어서 "안 보냄"과 구분이 필요합니다. API는 `exclude_unset`으로 보낸 필드만 넘김.
- **서비스는 아무 변경도 없는 `update`를 오류로 보지 않음**(그냥 현재 값을 돌려줌). "빈 본문 거부"는 API/스키마 계층의 책임으로 둠(TASK-049).
- 서비스는 커밋하지 않고 flush만 합니다(커밋은 요청 세션이 담당).

## 비고
- **미구현(TODO)**: 프로젝트를 휴지통으로 보낼 때 그 프로젝트의 Task도 함께 휴지통으로 보내야 하지만 Task 모델이 아직 없습니다. `soft_delete`에 `TODO(Phase 5/10)` 주석을 남겼고, Task 모델이 생기는 Phase 5(또는 휴지통 Phase 10)에서 처리해야 합니다.
- 다음 작업: T045 (소유권 검증).
