# TASK-015. API 라우터 구조 (/api/v1)

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
건물 1층에 "API 안내 데스크"를 만들고, 앞으로 생길 모든 기능(로그인, 프로젝트, 작업 등)이 이 데스크 아래 `/api/v1/...` 주소로 들어오게 한 작업입니다. `backend/src/api/router.py`에 버전 접두사가 붙은 `api_router`(`/api/v1`)를 만들고 앱에 연결했습니다. 이후 Task에서 `auth`, `projects` 같은 기능별 라우터를 이 라우터에 `include_router`로 붙이면 됩니다. 프론트엔드의 `VITE_API_BASE_URL=http://localhost:8000/api/v1`이 가리키는 곳이 바로 여기입니다.

## 변경 파일
- `backend/src/api/__init__.py`, `backend/src/api/router.py` (신규)
- `backend/src/main.py` (`api_router`를 포함하고, `/health` 핸들러를 `router.py`의 것을 재사용)
- `backend/tests/unit/test_router.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T015 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.api.router` 없음으로 수집 실패 확인
- GREEN: 구현 후 첫 실행에서 통과
- REFACTOR: Ruff/Black/MyPy(strict) 정리. 전체 113개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 내용: 접두사 `/api/v1`, `/api/v1/health` 200, OpenAPI에 노출, 버전 없는 `/api/health`와 `/api/v2/...`는 404, 하위 라우터를 접두사 아래에 붙일 수 있음, 요청 ID/처리 시간 헤더 적용

## 기술 결정
- `/api/v1/health`를 둔 이유: 라우터에 경로가 하나도 없으면 연결 여부를 확인할 수 없고, 프론트엔드가 `VITE_API_BASE_URL` 기준으로 서버 상태를 확인할 수 있어야 하기 때문. 기존 루트 `/health`는 인프라 점검용으로 유지하고 두 경로가 같은 핸들러를 공유함.
- 버전 접두사는 `API_PREFIX` 상수로 한 곳에서 관리해 이후 `/api/v2` 도입 시 영향 범위를 줄임.
- 헌법의 계층 규칙에 따라 라우터는 요청/응답 처리만 담당. 비즈니스 로직은 이후 Service 계층에 둠.
- 기능별 라우터(auth 등)는 해당 Task에서 추가. 지금 빈 라우터를 미리 만들지 않음(YAGNI).

## 비고
- 검증 중 Docker Desktop이 꺼져 DB 테스트 21개가 건너뛰어지는 것을 발견하고 Docker Desktop을 다시 실행해 전부 실행되도록 확인함. (날짜가 바뀌면 반복될 수 있음)
- 다음 작업: T016 (오류 처리 미들웨어와 예외 스키마), T017 (Celery).
