# TASK-002. 백엔드 Python 프로젝트 초기화 (FastAPI 의존성)

## 상태
완료

## 날짜
2026-10-27

## 작업 요약
요리 전에 장보기 목록을 만드는 것처럼, 백엔드가 쓸 라이브러리 목록 `backend/requirements.txt`를 작성했습니다.
웹 서버(FastAPI, Uvicorn), 데이터 검증(Pydantic), 데이터베이스(SQLAlchemy 2.0, asyncpg, Alembic), 로그인 보안(PyJWT, bcrypt), 백그라운드 작업(Celery, Redis), AI 연동(google-genai), 테스트(pytest 계열, httpx), 코드 품질 도구(Ruff, Black, MyPy)를 담았습니다.

## 변경 파일
- `backend/requirements.txt` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T002 체크)

## TDD 결과
- RED 커밋: 해당 없음 (설정 파일 작업으로 테스트 대상 코드 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: `pip install --dry-run -r requirements.txt`로 모든 의존성이 충돌 없이 설치 가능함을 확인 (Python 3.12.10). 실제 설치는 하지 않음.

## 기술 결정
- 버전은 하한(`>=`)과 필요한 곳만 상한으로 지정. 정확한 고정(lock)은 추후 필요 시 도입.
- JWT는 `PyJWT`, 비밀번호는 `bcrypt`를 직접 사용 (research.md의 JWT + bcrypt 결정, passlib 미사용으로 의존성 최소화).
- DB 드라이버는 비동기용 `asyncpg`와 Alembic 마이그레이션용 `psycopg2-binary`를 함께 포함.
- Gemini는 현행 SDK인 `google-genai` 사용.
- 테스트/린트 도구는 constitution(pytest, Ruff, Black, MyPy)에 맞춰 포함. 설정 파일(pyproject.toml)은 T006에서 작성.

## 비고
- 가상환경 생성과 실제 설치는 수행하지 않았습니다.
- 다음 작업: T003 (프론트엔드 React + Vite 초기화).
