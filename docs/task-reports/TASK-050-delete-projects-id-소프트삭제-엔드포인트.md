# TASK-050. DELETE /projects/{project_id} 엔드포인트 (소프트 삭제)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
프로젝트를 휴지통으로 보내는 창구입니다. `DELETE /api/v1/projects/{project_id}` → `204 No Content`(본문 없음).
- 행을 지우지 않고 `deletion_status='trashed'`, `trashed_at`=지금, `scheduled_deletion_at`=30일 뒤로 표시.
- 이미 휴지통인 프로젝트를 다시 삭제하면 `404 project_not_found`. 없는 ID 404, 남의 프로젝트 403(그리고 그대로 유지).
- 삭제 후 목록과 단건 조회에서 사라집니다. 같은 사용자의 다른 프로젝트는 영향 없음.

## 변경 파일
- `backend/src/api/projects.py`, `backend/tests/integration/test_projects_api_db.py`

## TDD 결과
- RED: 테스트 먼저 작성 → 실패 확인
- GREEN: 구현 후 통과
- REFACTOR: Ruff/Black/MyPy 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (이 Task 범위)
- **커밋 확인**: 실제 `get_session` + 다른 세션이 `trashed` 상태, `trashed_at`, `scheduled_deletion_at`을 읽음. 사용자를 삭제하면 프로젝트도 함께 삭제됨(DB CASCADE)을 실제 커밋 데이터로 확인.
- 그 밖의 검증: 204에 본문 없음, 두 번째 삭제 404, 형식이 틀린 ID 422, OpenAPI에 5개 작업(`GET/POST /projects`, `GET/PATCH/DELETE /projects/{project_id}`)이 올바른 태그와 상태 코드(201, 204)로 등록됨

## 기술 결정
- 라우터는 `Response(status_code=204)`를 직접 돌려줘 본문이 비게 함(`logout`과 같은 방식).

## 비고
- **미구현**: 프로젝트의 Task도 함께 휴지통으로 보내는 일은 Task 모델이 없어 못 했습니다. `ProjectService.soft_delete`에 `TODO(Phase 5/10)` 표시가 있고, Phase 5(Task 모델)나 Phase 10(휴지통)에서 구현 후 이 서비스 메서드의 테스트에 "Task도 휴지통" 케이스를 추가해야 합니다.
- **Phase 10(휴지통)**: 휴지통 목록/복구/영구 삭제는 `deletion_status='trashed'`, `scheduled_deletion_at`을 사용하면 됩니다. 현재 `_owned_active_project`는 휴지통 항목을 404로 취급하므로 복구용 조회는 별도 메서드가 필요합니다.
- **Phase 5(Task 개수)**: 응답에 Task 개수는 아직 없습니다. 추가하려면 `ProjectResponse` 확장과 프런트엔드 협의가 필요합니다. 또 Task 활동 시 `last_activity_at`을 갱신하는 코드는 Phase 5에서 구현.
- 이 Task로 프로젝트 슬라이스 백엔드(T043~T050) 완료.
