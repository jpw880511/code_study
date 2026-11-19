# TASK-049. PATCH /projects/{project_id} 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
프로젝트의 제목/설명을 고치는 창구입니다. `PATCH /api/v1/projects/{project_id}` 본문 `{"title"?: str, "description"?: str|null}` → `200 ProjectResponse`(수정된 프로젝트).
- **부분 수정**: 본문에 있는 필드만 바뀝니다. `"description": null`(또는 공백)은 설명 지우기. `"title": null`/공백은 `422 invalid_project_title`.
- 본문이 `{}`이거나 알려진 필드가 하나도 없으면(`{"unknown": 1}` 포함) `422 validation_error`. 알려지지 않은 필드는 다른 유효한 필드와 같이 오면 무시됩니다(`user_id`, `deletion_status` 등으로 소유자/상태를 바꿀 수 없음).
- `updated_at`만 갱신되고 `last_activity_at`은 그대로. 마지막 쓰기가 이기는 방식(낙관적 잠금 없음, Phase 1 MVP 방침).
- 소유권: 없음/휴지통 404, 남의 프로젝트 403(403이 값 검증보다 먼저). 거부된 요청은 아무것도 바꾸지 않음.

## 변경 파일
- `backend/src/api/projects.py`, `backend/src/api/schemas.py`(`ProjectUpdate`)
- `backend/tests/integration/test_projects_api_db.py`

## TDD 결과
- RED: 테스트 먼저 작성 → 실패 확인
- GREEN: 구현 후 통과
- REFACTOR: Ruff/Black/MyPy 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 신규 코드 100%
- **커밋 확인**: 실제 `get_session` + 다른 세션으로 읽어 제목 변경, 설명이 NULL이 되었음, `updated_at > created_at`을 확인
- 그 밖의 검증: 제목만/설명만/둘 다, 응답이 이후 GET과 동일, 너무 긴 값은 아무것도 바꾸지 않음, 타입 오류(`title: 5`) → `validation_error`, 남의 프로젝트에 빈 제목을 보내도 403

## 기술 결정
- "present vs omitted"는 pydantic의 `model_fields_set`과 `model_dump(exclude_unset=True)`로 구분하고, 서비스의 `UNSET` 센티넬로 전달.
- "빈 본문 거부"는 스키마의 `model_validator`가 담당(서비스는 변경 없는 호출을 허용). 응답 형식은 기존 `validation_error` 핸들러를 그대로 사용.

## 비고
- 프런트엔드: PATCH는 바뀐 필드만 보내도 되고, 설명을 지우려면 `null`을 명시해야 합니다.
- 다음 작업: T050 (DELETE).
