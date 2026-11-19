# TASK-047. POST /projects 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
새 프로젝트를 만드는 창구입니다. `POST /api/v1/projects` 본문 `{"title": str, "description": str|null (선택)}` → `201 ProjectResponse`.
- 제목/설명은 서비스가 다듬고 검증합니다. 빈/공백 제목 → `422 invalid_project_title`("프로젝트 제목은 최소 1자 이상이어야 합니다."), 255자 초과 → 같은 코드("프로젝트 제목은 최대 255자까지 입력 가능합니다."), 설명 2000자 초과 → `422 invalid_project_description`, `title` 누락/타입 오류/깨진 JSON → `422 validation_error`.
- 본문의 `id`, `user_id`, `deletion_status`, `created_at` 같은 필드는 **무시**됩니다(스키마에 없음). 소유자는 항상 로그인한 사용자.
- `DbSession`을 사용해 응답이 나가기 **전에** 커밋됩니다.

## 변경 파일
- `backend/src/api/projects.py`, `backend/src/api/schemas.py`(`ProjectCreate`)
- `backend/tests/integration/test_projects_api_db.py`

## TDD 결과
- RED: 테스트 먼저 작성 → 실패 확인(T046과 같은 RED)
- GREEN: 구현 후 통과
- REFACTOR: Ruff/Black/MyPy 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 신규 코드 100%
- **커밋 확인**: 실제 `get_session`을 쓰는 테스트에서 **다른 세션**이 방금 만든 프로젝트를 읽음. 또 "응답 헤더가 시작되는 순간 다른 세션에서 이미 보이는지"를 감시하는 테스트로 커밋이 응답 전임을 증명. 거부된 요청(422/403)은 아무것도 저장하지 않음.
- 그 밖의 검증: 설명 없음/`null`/공백 → `description: null`, 최대 길이(255/2000자) 허용, `<script>`/SQL 문자열이 그대로 저장됨, NUL 문자 → 500이 아니라 422, 인증 실패 시 본문을 검증하지 않고 데이터도 건드리지 않음

## 기술 결정
- 제목 검증을 pydantic이 아닌 서비스에 둠: 오류 코드/메시지를 계약대로 `invalid_project_title`로 일관되게 내기 위해(pydantic 제약을 쓰면 `validation_error`가 됨).
- 생성 시 `last_activity_at` = `created_at`(응답에서 동일).

## 비고
- 다음 작업: T048 (GET 단건).
