# TASK-017. Celery 앱 및 Redis 연결

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
무거운 일(AI 문서 생성 등)을 요청 중에 직접 하지 않고 "주문표"로 적어 주방(백그라운드 작업자)에 넘기는 구조를 만든 작업입니다. Redis는 주문표를 꽂아 두는 꽂이 역할을 합니다. `backend/src/tasks/celery_app.py`에 다음을 구현했습니다.
- `RedisSettings`: `REDIS_URL`(기본 `redis://localhost:6379/0`)을 환경변수/`.env`에서 읽고 `redis://`, `rediss://` 외에는 거부.
- `create_celery_app()`: Celery 앱 생성. 큐 4개(`default`, `document_generation`, `practice_generation`, `cleanup`), 작업 제한 시간 300초, JSON 직렬화만 허용, UTC, 시작 상태 추적, 브로커 재연결.
- 모듈 수준 `celery_app` (작업자 실행: `celery -A src.tasks.celery_app worker --pool=solo`).

## 변경 파일
- `backend/src/tasks/__init__.py`, `backend/src/tasks/celery_app.py` (신규)
- `backend/tests/unit/test_celery_app.py`, `backend/tests/integration/test_redis_connection.py` (신규)
- `backend/pyproject.toml` (MyPy: celery/kombu 타입 정보 없음 처리, 테스트의 데코레이터 허용)
- `specs/001-ai-code-learning-platform/tasks.md` (T017 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.tasks.celery_app` 없음으로 수집 실패 확인
- GREEN: 구현 후 전체 통과
- REFACTOR: 구현 후 점검 중 큐 설정 보강 필요를 발견(아래 기술 결정). 큐별 교환기/라우팅 키 테스트를 먼저 추가해 실패를 확인한 뒤 수정. Ruff/Black/MyPy(strict) 정리. 전체 160개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 실제 Redis 검증(Docker): 브로커 연결, 결과 저장소 ping, 실제 Celery 작업자(`start_worker`)로 작업 왕복(4+5=9), 큐별 전달 확인. 또한 `celery worker` CLI를 직접 실행해 `inspect ping` 응답(pong)과 큐 4개 등록을 확인한 뒤 종료.

## 기술 결정
- 큐 이름과 300초 제한은 헌법(III. 비동기 처리)을 그대로 따름.
- 큐마다 별도의 교환기(exchange)와 라우팅 키를 명시. 처음에는 `Queue(name)`만 썼는데 이 경우 Celery가 4개 큐를 모두 교환기 `default`/라우팅 키 `default`에 묶습니다. 이번 Redis 환경에서는 실제로 다른 큐로 중복 전달되는 현상이 재현되지 않았지만(통합 테스트로 확인), RabbitMQ 같은 AMQP 브로커로 바꾸면 모든 큐에 복사되어 작업이 중복 실행될 수 있어 예방 차원에서 수정. 큐별 전달 테스트는 회귀 방지용으로 유지.
- JSON 직렬화만 허용해 신뢰할 수 없는 pickle 역직렬화 위험을 차단.
- Windows에서는 기본 prefork 풀이 동작하지 않으므로 개발 시 `--pool=solo`를 사용.
- Redis 캐시용 클라이언트 헬퍼는 아직 사용처가 없어 만들지 않음 (YAGNI). 필요해지면 해당 Task에서 추가.
- 매일 새벽 2시 휴지통 정리 같은 예약 작업(beat 스케줄)은 해당 기능 Task에서 추가.

## 비고
- 통합 테스트는 개발 데이터와 섞이지 않도록 Redis DB 15번을 사용하고 시작/종료 시 비움. Redis에 접속할 수 없으면 실패가 아니라 건너뜀(skip)으로 처리되므로 건너뜀 개수도 확인해야 함.
- 테스트 실행 시 `starlette.testclient`의 httpx deprecation 경고 1건 (기능 영향 없음).
- 다음 작업: Phase 2 프론트엔드 기반 T018~T022.
