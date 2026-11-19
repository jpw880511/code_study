# TASK-068. TaskService (생성·조회·목록·수정·소프트 삭제)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
프로젝트 안의 Task를 다루는 `TaskService`를 만들었다. HTTP를 모르고 `DomainError` 서브클래스만 던지며 커밋하지 않는다(요청 세션이 커밋).
- `create`: 프로젝트 소유권 확인 → 제목·설명 검증 → 프로젝트 행 `SELECT … FOR UPDATE` → `MAX(task_number)+1`(휴지통 Task 포함) → 저장. `projects.last_activity_at` 갱신.
- `get`: 업로드와 파일을 함께 읽는다. `list`: 활성 Task를 `task_number` 오름차순으로, 업로드 요약과 함께.
- `update`: 보낸 필드만 변경(`description=None`이면 지움). 번호·업로드 방식은 바꾸지 않는다. 활동 시각 갱신.
- `soft_delete`: `deletion_status='trashed'`, `trashed_at=now`, `scheduled_deletion_at=+30일`, 활동 시각 갱신.
- 소유권·휴지통 검사는 `_owned_active_task` 한 곳: 없는 Task, 휴지통 Task, 휴지통 프로젝트의 Task는 404 `task_not_found`, 남의 것은 403 `task_forbidden`. 프로젝트 쪽 검사는 `ProjectService`를 재사용.
- 제목(5~255자, NUL 금지)·설명(500자 이하, 공백만이면 null, NUL 금지) 검증은 계약의 코드·메시지로 응답.
- **`ProjectService.soft_delete` 수정**: 프로젝트를 휴지통에 보낼 때 활성 Task도 같은 `trashed_at`/`scheduled_deletion_at`으로 보낸다(이미 휴지통인 Task는 그대로). TODO 주석을 제거했다.

## 변경 파일
- `backend/src/services/task_service.py`, `backend/src/services/task_errors.py` (신규)
- `backend/src/services/project_service.py` (소프트 삭제 시 Task 휴지통 이동)
- `backend/src/api/exceptions.py` (`DOMAIN_ERROR_STATUS`에 Task 관련 코드)
- `backend/tests/unit/test_task_validation.py` (신규, 16개)
- `backend/tests/integration/test_task_service_db.py` (신규, 43개)
- `backend/tests/integration/test_task_number_concurrency_db.py` (신규, 2개)
- `backend/tests/integration/test_project_service_db.py` (프로젝트 삭제 시 Task 이동 3개 추가)
- `backend/tests/unit/test_domain_errors.py` (상태 표 기대값에 새 코드 추가, 기존 항목은 그대로)

## TDD 결과
- RED: `task_service`/`task_errors`가 없어 수집 단계 `ModuleNotFoundError`.
- GREEN: 신규 통과. 소유권 표(본인/남/없음/휴지통/휴지통 프로젝트 × get·update·delete), 번호 규칙(프로젝트별, 휴지통 번호 재사용 금지), 검증 실패 시 아무것도 저장되지 않음, 남의 Task는 잘못된 입력이어도 403.
- **동시성**: 서로 다른 연결 8개가 실제 커밋으로 동시에 만들어도 번호가 1~8로 겹치지 않음. 또 한 연결이 커밋 전에 프로젝트 행을 잡고 있으면 두 번째 생성이 0.5초 안에 끝나지 않고(잠금 대기), 첫 커밋 후 번호 2를 받음 — 잠금이 없으면 둘 다 1을 계산하므로 잠금 자체를 증명한다.
- 기존 프로젝트 테스트 전부 통과(`test_domain_errors`의 상태 표 동등 비교만 새 코드를 포함하도록 확장).
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 잠금은 소유권 확인 **뒤**에 건다(남이 잠금 경쟁을 일으키지 못하게). 잠금 후 프로젝트 행을 다시 읽어(`populate_existing`) 기다리는 동안 휴지통에 갔는지 재확인한다.
- `updated_at`은 DB의 `now()`(트랜잭션 시작 시각)라, 롤백되는 단일 트랜잭션 테스트에서는 변화를 볼 수 없어 서비스 테스트에서는 `updated_at` 증가를 검사하지 않는다(활동 시각은 파이썬 시각이라 검사함).
- 휴지통 이동은 프로젝트 삭제와 같은 시각을 쓰는 단일 `UPDATE`로 처리했다.

## 비고
- 복원·영구 삭제·휴지통 목록은 요청 범위가 아니라 만들지 않았다.
- 프로젝트 삭제가 휴지통 Task의 파일을 지우지는 않는다(복원·30일 보관 때문).
