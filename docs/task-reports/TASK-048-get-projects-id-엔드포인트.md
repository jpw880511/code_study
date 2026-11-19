# TASK-048. GET /projects/{project_id} 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
프로젝트 하나를 보여 주는 창구입니다. `GET /api/v1/projects/{project_id}` → `200 ProjectResponse`.
- 없음 또는 휴지통 → `404 project_not_found`("요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다.")
- 남의 활성 프로젝트 → `403 project_forbidden`("이 프로젝트에 접근할 권한이 없습니다."). 응답에는 제목/설명/ID가 전혀 없음.
- 경로의 UUID 형식이 틀리면 `422 validation_error`(FastAPI 기본 동작).

## 변경 파일
- `backend/src/api/projects.py`, `backend/tests/integration/test_projects_api_db.py`

## TDD 결과
- RED: 테스트 먼저 작성 → 실패 확인
- GREEN: 구현 후 통과
- REFACTOR: 소유권 검사는 서비스의 한 곳을 재사용(라우터에 로직 없음)
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 신규 코드 100%
- 검증 범위: 응답이 생성 응답과 동일, 없는 ID, 남의 프로젝트(403, 응답 텍스트에 남의 데이터 없음), 본인 휴지통(404), 형식이 틀린 ID 4종(`not-a-uuid`, `123`, 짧은 UUID, SQL 문자열) → 422, 두 사용자 교차 접근

## 기술 결정
- 휴지통 프로젝트를 404로 처리하는 이유는 TASK-045 참고. 휴지통 조회/복구는 Phase 10(휴지통 API)에서 별도 엔드포인트로 제공 예정.

## 비고
- 다음 작업: T049 (PATCH).
