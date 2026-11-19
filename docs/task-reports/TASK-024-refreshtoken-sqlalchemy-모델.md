# TASK-024. RefreshToken SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-05

## 작업 요약
로그인 상태를 유지하는 "재발급 이용권"을 데이터베이스에 기록하는 `refresh_tokens` 표의 코드판(모델)입니다. 이용권 원본은 저장하지 않고 **해시(SHA-256)만** 저장합니다. `backend/src/models/refresh_token.py`의 `RefreshToken`은 T009 마이그레이션과 같은 열을 가집니다.
- `id`(DB 자동 생성), `user_id`(필수, `users.id`를 가리키는 외래키, 사용자 삭제 시 함께 삭제), `token_hash`(255자, 필수, 중복 불가), `expires_at`(필수, 만료 시각), `created_at`(DB 기본값), `revoked`(기본값 false), `revoked_at`(폐기 시각, 비어 있을 수 있음).
- 인덱스 3개(`idx_refresh_tokens_user_id`, `idx_refresh_tokens_hash`, `idx_refresh_tokens_expires`)도 같은 이름으로 정의.
- `updated_at`은 이 표에 없으므로 갖지 않음. `repr()`은 id와 user_id만 보여주고 해시는 숨김.
- **T023 보고서에서 약속한 사용자와의 관계를 추가**: `User.refresh_tokens`(한 사용자에 이용권 여러 개)와 `RefreshToken.user`(이용권의 주인).

## 변경 파일
- `backend/src/models/refresh_token.py` (신규), `backend/src/models/__init__.py`
- `backend/src/models/user.py` (`refresh_tokens` 관계 추가)
- `backend/src/models/base.py` (`CreatedAtMixin` 분리)
- `backend/tests/unit/test_refresh_token_model.py`, `backend/tests/integration/test_refresh_token_model_db.py` (신규)
- `backend/tests/unit/test_base.py` (`CreatedAtMixin` 테스트 추가)
- `backend/tests/conftest.py` (롤백되는 비동기 `session` 픽스처를 공용으로 이동), `backend/tests/integration/test_user_model_db.py` (픽스처 제거)
- `specs/001-ai-code-learning-platform/tasks.md` (T024 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `RefreshToken`과 `CreatedAtMixin`을 불러올 수 없어 수집 단계에서 실패 확인
- GREEN: 구현 후 첫 실행에서 전체 통과
- REFACTOR: 테스트 린트/타입 정리(불필요한 캐스트, 긴 줄) 후 재실행. Ruff/Black/MyPy(strict) 통과. 전체 215개 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 범위
  - 코드만으로: 열 구성(`updated_at` 없음), 외래키와 `ON DELETE CASCADE`, 길이/NULL/기본값, 인덱스 3개, `repr`, 관계 설정(양방향, 삭제 전파, 지연 로딩 금지)
  - 실제 PostgreSQL로: 저장 후 즉시 값 확인, 폐기 기록, 해시로 조회, 해시 중복/255자 초과/사용자 누락/만료 시각 누락/존재하지 않는 사용자 거부, 사용자별 이용권 목록, 사용자 삭제 시 이용권 삭제(다른 사용자의 것은 유지), 목록에서 제거하면 행 삭제
  - 모델이 실제 마이그레이션된 DB 구조(열, 타입, 길이, NULL, 기본값, 외래키, 인덱스, 유일 제약)와 일치하는지 비교

## 기술 결정
- **`CreatedAtMixin` 분리.** 이 표처럼 `created_at`만 있는 표가 앞으로 4개(uploaded_code, code_files, practice_problems, questions) 더 있어서, `TimestampMixin`이 `CreatedAtMixin`을 상속하고 `updated_at`만 더하는 구조로 바꿨습니다. 기존 모델에는 영향 없음.
- **관계를 `lazy="raise"`로 설정.** 비동기 코드에서는 관계를 뒤늦게 자동으로 읽어 올 수 없습니다. 실수로 접근하면 모호한 오류 대신 바로 명확한 오류가 나고, 필요한 곳에서 `selectinload(User.refresh_tokens)`처럼 명시적으로 불러오도록 강제합니다(테스트로 고정).
- **삭제는 DB에 맡김(`passive_deletes=True`).** DB가 `ON DELETE CASCADE`로 이용권을 지우므로, ORM이 사용자를 지울 때 이용권을 먼저 읽어 오지 않음. 목록에서 빼면 행이 삭제되도록 `delete-orphan`도 설정.
- **`revoked`는 마이그레이션 그대로 NULL을 허용.** 마이그레이션에 `NOT NULL`이 없어서 그대로 맞췄습니다. 기본값이 false라 실제로는 거의 NULL이 아니지만, 코드는 NULL도 "폐기 안 됨"으로 처리해야 합니다(아래 비고).
- 만료/폐기 판단 같은 업무 로직은 모델에 넣지 않음. 헌법상 모델은 구조만 담당하고 로직은 TokenService(T026)가 맡음.
- 공용 `session` 테스트 픽스처를 `conftest.py`로 옮겨 두 DB 테스트 파일이 함께 사용. 이동 전후 186개 통과로 동작 불변을 확인.

## 비고
- **T026(TokenService)에서 할 일:** 이용권이 유효한지 판단할 때 `revoked`가 NULL이거나 false이면 폐기 안 됨으로, `expires_at`이 현재보다 뒤여야 유효로 처리해야 합니다. 갱신 시 이전 이용권을 폐기(`revoked=True`, `revoked_at`)하고 새 것을 발급하는 순환(rotation)도 거기서 구현.
- 만료된 이용권을 주기적으로 지우는 작업은 설계서에 없어 만들지 않음. 필요해지면 정리용 Celery 작업으로 추가.
- 다음 작업: T025 (UserService), T026 (TokenService), T027 (인증 의존성).
