# TASK-009. Base 모델 클래스 및 초기 DB 스키마 마이그레이션

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
집을 지을 때 먼저 "설계도 양식"(Base 모델)과 "건물 뼈대"(초기 마이그레이션)를 만드는 작업입니다.
- `backend/src/models/base.py`: 모든 모델이 공통으로 쓰는 `Base`(제약조건 이름 규칙 포함), 고유번호(UUID) 기본키 `UUIDPrimaryKeyMixin`, 생성/수정 시각 `TimestampMixin`.
- `backend/alembic/versions/001_initial_schema.py`: data-model.md의 10개 테이블(users, projects, tasks, uploaded_code, code_files, learning_documents, practice_problems, questions, progress, refresh_tokens)과 모든 인덱스를 직접 작성한 SQL로 생성. `downgrade`는 역순으로 삭제.

## 변경 파일
- `backend/src/__init__.py`, `backend/src/models/__init__.py`, `backend/src/models/base.py` (신규)
- `backend/alembic/versions/001_initial_schema.py` (신규)
- `backend/tests/__init__.py`, `tests/conftest.py` (신규)
- `backend/tests/unit/test_base.py`, `backend/tests/integration/test_initial_migration.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T009 체크)

## TDD 결과
- RED: 테스트 먼저 작성 후 실행 → `src.models.base` 없음(ImportError), 마이그레이션 없음(테이블 생성 테스트 실패) 확인
- GREEN: 구현 후 22개 테스트 모두 통과
- REFACTOR: Ruff/Black/MyPy(strict) 정리 후 재실행하여 22개 통과 유지
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (base.py 12문장)
- 검증 범위: 10개 테이블 및 인덱스 존재, 기본값, CHECK(이메일 형식, 제목 길이, 업로드 크기, 확장자, 7개 챕터 JSONB, 문제 번호 1~5, 질문 길이, 진행률 범위), UNIQUE, CASCADE 삭제, `downgrade`로 전체 제거

## 기술 결정
- 테스트는 개발용 DB를 건드리지 않도록 임시 DB `codelearning_test`를 만들고 끝나면 삭제. PostgreSQL에 접속할 수 없으면 skip. 접속 정보는 `TEST_ADMIN_DATABASE_URL`로 변경 가능.
- `learning_documents`의 7개 챕터 검사는 `content ? 'chapterN'` 7번 대신 `content ?& ARRAY[...]`(모든 키 포함)로 동일한 의미를 더 간결하게 작성.
- 설계서에는 `created_at/updated_at`에 DEFAULT만 있었으나, 모델의 `TimestampMixin`(nullable=False)과 일치하도록 DB에도 `NOT NULL`을 추가함. `last_activity_at` 등 다른 시각 컬럼은 설계서 그대로.
- `updated_at` 자동 갱신 트리거는 설계서에 없어 만들지 않음. 서비스 계층에서 갱신해야 함.
- 제약조건 이름 규칙(naming convention)을 지금 정해 두어 이후 모델/마이그레이션의 이름이 일관되게 함.
- 마이그레이션은 `op.execute`에 SQL을 직접 사용(autogenerate 금지 요구). 정규식의 `\.`를 위해 raw 문자열 사용.

## 비고
- 개발용 DB(`codelearning`)에도 upgrade → downgrade를 확인했고, 현재 base 상태(테이블 없음)로 되돌려 둠. 적용하려면 `DATABASE_URL`을 설정하고 `alembic upgrade head`.
- `Base`와 mixin은 아직 실제 모델에서 쓰이지 않음(T023 이후에서 사용). 모델은 이 마이그레이션 스키마와 일치해야 함.
- 다음 작업: T010 (DB 세션 관리), T011 (DB 설정/커넥션 풀).
