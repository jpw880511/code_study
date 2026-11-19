# TASK-014. FastAPI 앱 초기화 (CORS, 미들웨어)

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
건물의 정문(서버 입구)을 세우는 작업입니다. 허가된 방문자만 들이는 출입 명단(CORS), 방문자마다 번호표를 붙이고 처리 시간을 재는 안내 데스크(미들웨어), 건물이 열려 있는지 확인하는 인터폰(`/health`)을 만들었습니다.
- `backend/src/main.py`: `create_app()` 앱 팩토리와 모듈 수준 `app`. CORS, 요청 메타데이터 미들웨어, `GET /health`, 종료 시 DB 연결 정리(lifespan). `/docs`, `/openapi.json`은 FastAPI가 자동 제공.
- `backend/src/config.py`: `AppSettings` (`ENVIRONMENT`, `DEBUG`, `ALLOWED_ORIGINS`를 환경변수/`.env`에서 읽음).
- CORS: 명시한 출처만 허용하고 쿠키(자격 증명) 허용. 와일드카드(`*`)는 설정 단계에서 거부.
- 미들웨어: 모든 응답에 `X-Request-ID`(요청 추적 번호)와 `X-Process-Time`(처리 시간, 초) 추가.

## 변경 파일
- `backend/src/main.py`, `backend/src/config.py` (신규)
- `backend/src/db/session.py` (`dispose_engine`이 연결을 만든 적 없으면 아무 것도 하지 않도록 수정)
- `backend/tests/unit/test_main.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T014 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.config` 없음으로 수집 실패 확인
- GREEN: 구현 후 첫 실행에서 전체 통과
- REFACTOR: Ruff/Black/MyPy(strict) 정리 후 전체 104개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 추가 검증: 실제 uvicorn으로 서버를 띄워 `/health`(200, CORS·요청 ID 헤더 확인), `/docs`(200) 확인 후 종료

## 기술 결정
- 앱 팩토리 `create_app(settings)`로 테스트마다 다른 설정의 앱을 만들 수 있게 함.
- CORS는 `allow_credentials=True`(쿠키 기반 JWT)이므로 브라우저 규칙상 와일드카드 불가 → 설정 검증에서 거부. 허용 메서드/헤더도 필요한 것만 나열.
- `ALLOWED_ORIGINS`는 `.env`에 쉼표로 구분해 적는 형식(`NoDecode`로 JSON 파싱 대신 쉼표 분리).
- 클라이언트가 보낸 `X-Request-ID`는 `[A-Za-z0-9._-]{1,64}`일 때만 사용하고, 그 외(공백, 줄바꿈, 스크립트 등)는 새로 생성 → 로그 위조/주입 방지.
- `dispose_engine`을 연결 미생성 시 no-op으로 바꿔서, DB 설정 없이도 앱이 시작/종료될 수 있게 함.
- `/api/v1` 라우터 연결은 T015, 예외 처리 미들웨어는 T016에서 추가.

## 비고
- 테스트 실행 시 `starlette.testclient`가 httpx 사용을 deprecated로 표시하는 경고 1건이 있음 (기능 영향 없음). Starlette가 `httpx2`를 권장하는 방향이라 추후 의존성 정리 때 확인.
- 실행: `cd backend; .venv/Scripts/uvicorn src.main:app --reload` → http://localhost:8000/docs
- 다음 작업: T015 (API 라우터 구조 /api/v1), T016 (오류 처리), T017 (Celery).
