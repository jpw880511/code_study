# TASK-010. 데이터베이스 연결 및 세션 관리

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
식당에서 손님(요청)마다 전담 서빙 직원(세션)을 한 명씩 배정하고, 주문이 무사히 끝나면 계산(commit), 문제가 생기면 주문 취소(rollback)하는 방식과 같습니다. `backend/src/db/session.py`에 다음을 구현했습니다.
- `to_async_url`: `postgresql://`, `postgres://` 주소를 비동기 드라이버(`postgresql+asyncpg://`)용으로 변환. PostgreSQL이 아니면 오류.
- `create_engine`, `create_session_factory`: 비동기 엔진과 세션 공장 생성 (`expire_on_commit=False`).
- `get_session_factory`: `DATABASE_URL` 환경변수로 한 번만 만들어 재사용. 값이 없으면 명확한 오류.
- `get_session`: FastAPI 의존성. 요청당 세션 1개, 성공 시 commit, 예외 시 rollback.
- `dispose_engine`: 앱 종료 시 연결 정리.

## 변경 파일
- `backend/src/db/__init__.py`, `backend/src/db/session.py` (신규)
- `backend/tests/unit/test_session.py`, `backend/tests/integration/test_db_session.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T010 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.db.session` 없음으로 수집 단계 실패 확인
- GREEN: 구현 후 1건 실패(`postgres://` 별칭이 SQLAlchemy에서 백엔드명 `postgres`로 인식됨) → 구현을 수정해 통과 (테스트는 수정하지 않음)
- REFACTOR: Ruff/Black/MyPy(strict) 정리, `get_session` 반환 타입을 `AsyncGenerator`로 명확화 후 전체 32개 테스트 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%

## 기술 결정
- research.md의 결정에 따라 asyncpg 기반 비동기 SQLAlchemy 사용. Alembic은 동기 URL을 그대로 쓰므로, 하나의 `DATABASE_URL`에서 동기/비동기 주소를 모두 파생.
- commit/rollback을 의존성에서 처리해 API 계층에서 트랜잭션 코드를 쓰지 않게 함 (헌법의 계층 규칙 준수).
- 커넥션 풀 크기 등 세부 설정은 T011(`db/config.py`) 범위라 `create_engine`의 `**engine_options`로 받을 수만 있게 열어 둠. YAGNI로 풀 설정은 여기서 하드코딩하지 않음.
- 테스트는 임시 DB(`codelearning_test`)에서 실제 PostgreSQL로 commit/rollback 동작을 검증.

## 비고
- T011에서 `config.py`가 생기면 `get_session_factory`가 환경변수를 직접 읽는 부분을 설정 객체로 바꾸는 작은 리팩토링이 필요할 수 있음.
- 다음 작업: T011 (DB 설정 및 커넥션 풀).
