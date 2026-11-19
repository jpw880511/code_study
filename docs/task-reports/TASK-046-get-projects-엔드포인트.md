# TASK-046. GET /projects 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
내 프로젝트 목록을 돌려주는 창구입니다. `GET /api/v1/projects` → `200 [ProjectResponse]`.
- 로그인 필수(`CurrentUser`). 본인의 **활성** 프로젝트만, `last_activity_at` 내림차순 → `created_at` 내림차순. 페이지 나누기 없음.
- 응답 항목은 정확히 `id, title, description, created_at, updated_at, last_activity_at` (`user_id`, 삭제 필드, Task 개수는 없음).
- 라우터는 서비스 호출과 응답 변환만 합니다. 이 Task에서 공통으로 쓰는 요소도 함께 만들었습니다: `projects_router`(`backend/src/api/projects.py`, `api_router`에 포함), `ProjectResponse`/`ProjectCreate`/`ProjectUpdate`(`backend/src/api/schemas.py`), `DomainError` 핸들러와 상태 코드 표 `DOMAIN_ERROR_STATUS`(`backend/src/api/exceptions.py`; 기존 `AUTH_ERROR_STATUS`는 그대로 두고 프로젝트 코드를 합침, 알 수 없는 코드는 400).

## 변경 파일
- `backend/src/api/projects.py` (신규), `backend/src/api/router.py`, `backend/src/api/schemas.py`, `backend/src/api/exceptions.py`
- `backend/tests/integration/test_projects_api_db.py` (신규; T046~T050 공통, 90개)

## TDD 결과
- RED: API 테스트 먼저 작성 → 수집 단계에서 실패 확인(`Project`/서비스 모듈 부재)
- GREEN: 구현 후 통과
- REFACTOR: 핸들러 이름을 `handle_auth_error` → `handle_domain_error`로 변경(`AuthError`도 그대로 처리됨; 기존 인증 테스트 전부 통과)
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/api/projects.py` 100%
- 검증 범위: 쿠키 없음(401 `not_authenticated`), 만료(401 `session_expired`), 리프레시 토큰/쓰레기 토큰, 삭제된 사용자의 토큰, 빈 배열, 응답 키 집합이 계약과 정확히 일치, 정렬(활동 시각 + 생성 시각 타이브레이커), 두 사용자의 목록 격리, 휴지통 항목 제외, 시각이 UTC ISO-8601

## 기술 결정
- 목록 응답에는 `response_model=list[ProjectResponse]`를 사용해, 모델에 컬럼이 추가돼도 응답에 새어 나가지 않음.
- 쓰기가 없는 엔드포인트지만 `CurrentUser`가 내부에서 `DbSession`을 쓰므로 동일한 요청 세션 흐름을 따름.

## 비고
- 다음 작업: T047 (POST).
