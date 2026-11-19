# TASK-073. PATCH /tasks/{task_id} 엔드포인트

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
Task의 제목·설명을 부분 수정한다. `PATCH /api/v1/tasks/{task_id}`, JSON `{title?, description?}` → `200 TaskResponse`.
- 보낸 필드만 바뀐다. `description: null`이면 설명을 지운다. `title: null`은 "보낸 필드"이므로 제목 규칙(5자 미만)으로 거부된다.
- 둘 다 없는 본문(`{}`, 알 수 없는 키만, 본문 없음)은 422 `validation_error`. 번호·업로드 방식·업로드는 바꿀 수 없다(본문에 보내도 무시).
- 제목 5~255자, 설명 500자 이하는 서비스가 검사해 422 `invalid_task_title`/`invalid_task_description`으로 응답한다. 실패하면 아무것도 바뀌지 않는다.
- 수정 시 `projects.last_activity_at`을 갱신한다.
- 응답은 수정 후의 `upload` 요약을 포함한다.

## 변경 파일
- `backend/src/api/tasks.py` (`update_task`), `backend/src/api/task_schemas.py` (`TaskUpdate`)
- `backend/tests/integration/test_tasks_api_db.py` (PATCH 관련 12개 안팎), `backend/tests/integration/test_tasks_api_commit_db.py`

## TDD 결과
- RED: 라우트 없음.
- GREEN: 통과. 부분 수정(제목만, 설명만), 앞뒤 공백 제거, `null` 설명 지우기, 잘못된 값 4종 422 후 변경 없음, 빈 본문 3종 422, `task_number`/`upload_method` 불변, 남의 Task 403, 없는/휴지통 Task 404, 실제 커밋 확인.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 프로젝트 `PATCH`와 같은 방식: `model_dump(exclude_unset=True)`를 서비스의 `UNSET` 센티널 인자로 넘긴다.
- 소유권 검사가 값 검증보다 먼저라서 남의 Task에 잘못된 값을 보내도 403이다.

## 비고
- 수정 후 `updated_at` 증가는 DB의 `now()`가 트랜잭션 시작 시각이라 롤백형 테스트로는 볼 수 없어, 응답 형식(ISO 시각, UTC)만 검사한다. 실제 커밋 테스트에서는 값 변경을 확인했다.
