# TASK-023. User SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-05

## 작업 요약
데이터베이스의 `users` 표(T009에서 만든 것)를 파이썬 코드에서 다룰 수 있게 해 주는 "표의 설계도"를 만든 작업입니다. `backend/src/models/user.py`의 `User`는 표와 똑같은 열을 가집니다.
- `id`(고유번호, DB가 자동 생성), `email`(255자, 중복 불가, 필수), `password_hash`(255자, 필수), `skill_level`(50자, 기본값 "Complete Beginner"), `created_at`, `updated_at`, `last_login_at`(시간대 포함, 마지막 로그인은 비어 있을 수 있음).
- 이메일 형식 검사 제약(`valid_email`)과 인덱스(`idx_users_email`)도 마이그레이션과 같은 이름으로 정의.
- `repr()`은 id와 이메일만 보여주고 비밀번호 해시는 절대 보여주지 않아, 로그에 실수로 찍혀도 해시가 새지 않음.
- `src/models/__init__.py`에서 `Base`, `User`를 내보냄.

## 변경 파일
- `backend/src/models/user.py` (신규), `backend/src/models/__init__.py`
- `backend/src/models/base.py` (아래 기술 결정 참고)
- `backend/tests/unit/test_user_model.py`, `backend/tests/integration/test_user_model_db.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T023 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `User`를 불러올 수 없어 수집 단계에서 실패 확인
- GREEN: 구현 후 통과. 한 번 이름 충돌(unit과 integration에 같은 파일명)로 수집이 실패해 DB 테스트 파일 이름을 `test_user_model_db.py`로 변경
- REFACTOR: Ruff/Black/MyPy(strict) 정리 후 전체 186개 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 범위
  - 코드만으로: 열 이름/타입/길이/NULL 허용/기본값/유일성, 인덱스, 제약 이름, `repr` 안전성
  - 실제 PostgreSQL(임시 DB)로: 저장 후 즉시 읽기(id, 기본값, 시간이 이미 채워져 있음), 이메일 조회, 마지막 로그인 기록, 중복 이메일과 잘못된 이메일 4종과 해시 누락과 255자 초과 거부, 서로 다른 id, `updated_at` 갱신
  - **모델이 실제 마이그레이션된 DB 구조와 일치하는지**: DB의 열/타입/길이/NULL/기본값/기본키/인덱스/유일 제약/체크 제약 이름을 읽어 모델과 비교

## 기술 결정
- **`Base`에 `eager_defaults=True` 설정.** 비동기 세션에서는 DB가 정한 값(id, 생성 시각 등)을 저장 직후 따로 읽어 올 수 없습니다(`MissingGreenlet` 오류). INSERT와 함께 받아 오도록 하여, 이후 모든 모델에서도 같은 문제가 생기지 않게 함.
- **`updated_at`에 ORM 갱신(`onupdate=now()`)을 추가.** T009 보고서에서 "수정 시각은 서비스 계층이 갱신해야 한다"고 적었는데, 이제 모델이 수정될 때마다 자동으로 갱신됩니다. DB 구조는 바뀌지 않음(트리거 아님). 같은 트랜잭션 안에서는 `NOW()`가 고정되므로, 이 동작은 실제 커밋 두 번으로 검증.
- **체크 제약 이름을 `conv("valid_email")`로 고정.** 이름 규칙(naming convention)을 그대로 적용하면 `ck_users_valid_email`이 되어 DB의 `valid_email`과 달라지기 때문.
- `skill_level`은 마이그레이션처럼 NULL을 허용(DB 기본값만 있음)하고, 기본값은 DB 쪽 기본값(`server_default`)으로 둠.
- 모델 검증을 "코드만으로 하는 테스트"와 "실제 DB 구조와 비교하는 테스트"로 나눠, 마이그레이션이 바뀌고 모델이 안 바뀌면(또는 반대) 바로 실패하게 함. 자동 생성(autogenerate)을 쓰지 않는 프로젝트 방침에서 두 정의가 어긋나는 것을 막는 안전장치.

## 비고
- **이메일 대소문자 주의(T025에서 처리):** DB의 형식 검사는 대소문자를 구분하지 않지만 중복 검사(UNIQUE)는 구분하므로, `A@x.com`과 `a@x.com`이 서로 다른 계정으로 저장될 수 있습니다. 회원가입과 로그인에서 이메일을 소문자로 정규화해야 합니다. 설계서에 규칙이 없어 모델에는 넣지 않고 UserService에서 결정하도록 남김.
- 관계(프로젝트, 리프레시 토큰)는 해당 모델이 만들어지는 Task(T024, T043)에서 추가.
- 개발 중 Docker Desktop이 꺼져 있어 다시 실행했음(날짜가 바뀌면 반복될 수 있음). DB 테스트는 연결이 안 되면 실패가 아니라 건너뛰므로 건너뜀 개수를 함께 확인해야 함.
- 다음 작업: T024 (RefreshToken 모델).
