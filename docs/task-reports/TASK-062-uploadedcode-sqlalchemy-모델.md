# TASK-062: UploadedCode SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
`uploaded_code` 테이블에 대응하는 `UploadedCode` 모델을 만들었다. 작업(Task)당 업로드 1건의 메타데이터(언어, 복잡도, 줄/파일 수, 크기)를 담으며, 마이그레이션(T009)의 컬럼·제약·인덱스 이름을 그대로 따른다. `Task.uploaded_code` ↔ `UploadedCode.task` 일대일 관계를 연결했다.

## 변경 파일
- `backend/src/models/uploaded_code.py` (신규)
- `backend/src/models/__init__.py` (`UploadedCode` 내보내기)
- `backend/src/models/task.py` (`Task.uploaded_code` 관계 추가)
- `backend/tests/unit/test_uploaded_code_model.py` (신규, 메타데이터 검증)
- `backend/tests/integration/test_uploaded_code_model_db.py` (신규, 실제 DB 검증)

## TDD 결과
- RED: `UploadedCode`가 없어 두 테스트 파일 모두 ImportError로 실패.
- GREEN: 신규 31개 통과. 전체 664개 통과(건너뜀 0), 커버리지 100%(835문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 검증한 규칙: 복잡도는 beginner/intermediate/advanced만 허용, 업로드 크기 10,485,760바이트(10MB)까지 허용하고 +1바이트는 거부, 작업당 업로드 1건(중복 시 `uploaded_code_task_id_key` 위반), 존재하지 않는 작업 참조 거부, 작업·프로젝트 삭제 시 DB가 업로드를 연쇄 삭제, 모델이 실제 마이그레이션된 스키마와 일치.

## 기술 결정
- 테이블에 `updated_at`이 없으므로 `TimestampMixin`이 아니라 `CreatedAtMixin`만 사용한다.
- 이름 없는 제약은 PostgreSQL이 붙인 이름(`uploaded_code_task_id_key`, `uploaded_code_complexity_level_check`)을 `conv()`로 그대로 지정한다.
- `task_id`의 유일성(UNIQUE)과 별도의 `idx_uploaded_code_task_id` 인덱스는 마이그레이션에 둘 다 있어 모델도 둘 다 선언했다(중복 인덱스지만 스키마와 일치시키는 것이 목표).
- 관계는 `lazy="raise"`, `passive_deletes=True`, `uselist=False`로 User↔Project, Project↔Task와 같은 규칙을 따른다.
- 10MB 한도는 `MAX_UPLOAD_SIZE_BYTES` 상수로 노출해 T064(파일 검증)가 재사용할 수 있게 했다.

## 비고
- `upload_size_bytes`는 INTEGER라 약 2GB까지 담을 수 있고, 10MB 한도는 CHECK 제약이 보장한다.
- `UploadedCode.code_files` 관계는 CodeFile 모델이 생기는 T063에서 추가한다.
- `ruff format --check`의 기존 지적(`tests/unit/test_token_service.py`)은 이번 작업과 무관하다.
