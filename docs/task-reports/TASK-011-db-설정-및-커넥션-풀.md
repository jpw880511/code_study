# TASK-011. 데이터베이스 설정 및 커넥션 풀

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
식당에서 "동시에 몇 명의 직원이 일할지"를 한곳에 적어 두는 근무 규정표를 만든 것과 같습니다. `backend/src/db/config.py`에 `DatabaseSettings`를 만들어 DB 주소와 커넥션 풀 설정(기본 크기 5, 추가 허용 10, 대기 한도 30초, 연결 재생성 주기 1800초, 사용 전 연결 확인, SQL 로그)을 환경변수(`DATABASE_URL`, `DB_POOL_SIZE` 등) 또는 루트 `.env`에서 읽도록 했습니다. 잘못된 값(예: 풀 크기 0)은 시작 시 거부합니다. `session.py`는 이제 이 설정을 사용해 엔진을 만듭니다.

## 변경 파일
- `backend/src/db/config.py` (신규)
- `backend/src/db/session.py` (설정 객체 사용으로 변경)
- `backend/tests/unit/test_db_config.py` (신규)
- `.env.example` (DB_POOL_* 항목 추가)
- `specs/001-ai-code-learning-platform/tasks.md` (T011 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.db.config` 없음으로 실패 확인
- GREEN: 구현 후 통과
- REFACTOR: `session.py`에서 직접 환경변수를 읽던 부분 제거(설정 한곳으로 통합), Ruff/Black/MyPy(strict) 정리. 전체 43개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%

## 기술 결정
- pydantic-settings 사용. `.env`는 프로젝트 루트에서 읽고, 같은 이름의 환경변수가 우선. 관련 없는 변수(GOOGLE_API_KEY 등)는 무시(`extra="ignore"`).
- `DATABASE_URL`만 접두사 없이, 나머지는 `DB_` 접두사로 통일.
- `DATABASE_URL`이 없을 때의 오류는 T010의 기존 테스트가 기대하는 `RuntimeError("DATABASE_URL ...")`를 유지하도록 `get_database_settings()`에서 변환.
- 풀 값 검증: pool_size ≥ 1, max_overflow ≥ 0, pool_timeout ≥ 1, pool_recycle ≥ -1.
- `pool_pre_ping=True`를 기본으로 해서 DB 재시작 후 끊어진 연결을 자동 복구.

## 비고
- 테스트 중 Docker Desktop이 꺼져 DB 테스트 21개가 건너뛰어지는 것을 발견하고 Docker Desktop을 다시 실행해 전부 실행되도록 확인함. DB 테스트는 PostgreSQL에 접속할 수 없으면 실패가 아니라 skip되므로, 건너뜀 개수도 함께 확인해야 함.
- 다음 작업: T012 (JWT 유틸리티), T013 (비밀번호 해싱) 등 Base Infrastructure.
