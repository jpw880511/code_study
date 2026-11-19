# TASK-061: Task SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
`tasks` 테이블에 대응하는 `Task` 모델을 만들었다. 마이그레이션(T009)의 컬럼, 제약, 인덱스와 같은 이름·같은 규칙을 유지하고, `Project.tasks` ↔ `Task.project` 관계를 연결했다.

## 변경 파일
- `backend/src/models/task.py` (신규)
- `backend/src/models/__init__.py` (`Task` 내보내기)
- `backend/src/models/project.py` (`Project.tasks` 관계 추가)
- `backend/tests/unit/test_task_model.py` (신규, 메타데이터 검증)
- `backend/tests/integration/test_task_model_db.py` (신규, 실제 DB 검증)

## TDD 결과
- RED: `Task`가 없어 두 테스트 파일 모두 ImportError로 수집 단계에서 실패.
- GREEN: 신규 36개 통과(건너뜀 0). 전체 633개 통과, 커버리지 100%(814문장, 미커버 0).
- 게이트: `ruff check src tests`, `mypy src` 통과.
- 검증한 규칙: 제목 5자 이상(5자 통과, 4자 거부), 설명 500자 이하(500 통과, 501 거부), `upload_method`는 file/folder/paste만, `deletion_status`는 active/trashed만, `(project_id, task_number)` 유일(다른 프로젝트에서는 같은 번호 허용), 프로젝트 삭제·사용자 삭제 시 DB가 작업을 연쇄 삭제, 모델이 실제 마이그레이션된 스키마와 일치.

## 기술 결정
- 제약 이름은 `conv()`로 DB의 이름을 그대로 쓴다. 이름이 없던 CHECK는 PostgreSQL이 붙인 `tasks_upload_method_check`, `tasks_deletion_status_check`를 따른다(Project 모델과 같은 방식).
- `task_number`는 DB 기본값이 없다. 프로젝트별 순차 번호 발급은 TaskService(T068)가 맡고, 모델은 유일성만 보장한다.
- 관계는 `lazy="raise"`(비동기 세션에서 암묵적 지연 로딩 금지), `passive_deletes=True`(삭제 연쇄는 DB에 맡김)로 User↔Project와 동일하게 했다.
- 프로젝트가 다른 모델(UploadedCode 등)과 맺는 관계는 해당 모델이 생기는 T062 이후에 추가한다.

## 비고
- `ruff format --check`는 이전부터 있던 `tests/unit/test_token_service.py` 1개에서 지적이 나온다. 이번 작업과 무관해 수정하지 않았다.
- 프로젝트 소프트 삭제 시 작업도 휴지통으로 옮기는 처리(`project_service.py`의 TODO)는 TaskService가 생긴 뒤 처리한다.
