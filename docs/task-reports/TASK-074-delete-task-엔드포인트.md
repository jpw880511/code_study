# TASK-074. DELETE /tasks/{task_id} 엔드포인트 (소프트 삭제)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
Task를 휴지통으로 보낸다. `DELETE /api/v1/tasks/{task_id}` → `204 No Content`(본문 없음).
- 행과 디스크 파일은 지우지 않는다. `deletion_status='trashed'`, `trashed_at=now`, `scheduled_deletion_at=+30일`.
- 삭제 후 `GET /tasks/{id}`, `GET /tasks/{id}/code`, 목록에서 사라지고(404/제외), 같은 Task를 다시 삭제하면 404. 삭제된 번호는 재사용되지 않는다(다음 Task는 번호 +1).
- 남의 Task 403(그대로 유지), 없는 Task 404, 로그인 없으면 401. `projects.last_activity_at` 갱신.
- 프로젝트를 삭제하면 활성 Task도 같은 시각으로 휴지통에 간다(TASK-068의 `ProjectService.soft_delete` 수정). 이후 Task의 GET·PATCH·DELETE·코드 조회는 모두 404이고, 실제 커밋된 데이터에서 `trashed_at`/`scheduled_deletion_at`이 프로젝트와 같음을 확인했다.

## 변경 파일
- `backend/src/api/tasks.py` (`delete_task`)
- `backend/tests/integration/test_tasks_api_db.py`, `backend/tests/integration/test_tasks_api_commit_db.py`

## TDD 결과
- RED: 라우트 없음.
- GREEN: 통과. 204 본문 없음, 행은 `trashed`, 30일 뒤 삭제 예약, 디스크 파일 1개 유지, 목록 비움, 번호 재사용 없음(삭제 후 새 Task는 2번), 두 번째 삭제 404, 남의 Task 403, 프로젝트 삭제 연쇄, 실제 커밋 확인.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 파일을 지우지 않는 이유는 복원과 30일 보관이다(계약 규칙 5). 영구 삭제는 Phase 10에서 만든다.

## 비고
- 복원·영구 삭제·휴지통 목록은 요청 범위가 아니라 만들지 않았다.
