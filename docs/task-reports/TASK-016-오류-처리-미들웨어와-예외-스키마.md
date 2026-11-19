# TASK-016. 오류 처리 미들웨어 및 예외 스키마

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
식당에서 어떤 문제가 생기든 손님에게 "같은 양식의 안내문"을 드리는 규칙을 만든 작업입니다. 어떤 오류가 나도 API가 항상 같은 모양의 JSON으로 답하고, 내부 사정(비밀번호, 코드 위치 등)은 절대 밖으로 새지 않게 했습니다. `backend/src/api/exceptions.py`에 다음을 구현했습니다.
- 응답 스키마 `ErrorResponse`: `error`(오류 코드), `message`(한국어 안내), 선택적으로 `details`, `suggestion`. (requirements-addendum.md의 "Error Response Format"을 따름)
- `AppError`와 하위 예외 `NotFoundError`(404), `ConflictError`(409), `UnauthorizedError`(401), `ForbiddenError`(403). 서비스 계층에서 던지면 자동으로 JSON 응답이 됩니다.
- 한국어 메시지 사전 `ERROR_MESSAGES` (같은 오류는 어디서나 같은 문구).
- 핸들러: `HTTPException`(404/405 등 포함, 헤더 보존), 요청 검증 오류(422, 필드 목록).
- `UnhandledErrorMiddleware`: 예상치 못한 예외를 잡아 일반 500 응답으로 바꾸고 로그에는 요청 번호와 함께 상세를 기록.

## 변경 파일
- `backend/src/api/exceptions.py` (신규)
- `backend/src/main.py` (핸들러/미들웨어 등록, `request.state.request_id` 저장)
- `backend/alembic/env.py` (`disable_existing_loggers=False`)
- `backend/tests/unit/test_exceptions.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T016 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.api.exceptions` 없음으로 수집 실패 확인
- GREEN: 구현 후 단독 실행은 통과, 전체 실행에서 로그 검증 테스트 1건 실패 → 원인은 Alembic `env.py`의 `fileConfig`가 이미 생성된 로거를 비활성화하던 것. 테스트를 고치지 않고 `env.py`에서 `disable_existing_loggers=False`로 수정해 해결
- REFACTOR: Ruff/Black/MyPy(strict) 정리. 비표준 상태 코드(599) 처리 분기 테스트 1건 추가. 전체 132개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%

## 기술 결정
- 검증 오류 응답에서 사용자가 보낸 입력값은 제거하고 필드명/메시지/유형만 반환. FastAPI 기본 응답은 입력값(`input`)을 그대로 돌려주어 비밀번호 같은 값이 새어 나갈 수 있기 때문 (테스트로 검증).
- 일반 `Exception` 핸들러 대신 미들웨어로 500을 처리하고 CORS와 요청 ID 미들웨어보다 안쪽에 배치. Starlette의 기본 500 처리는 가장 바깥에서 동작해 CORS 헤더가 빠지고, 브라우저에서 500이 CORS 오류로 보이는 문제가 생기기 때문 (테스트로 검증).
- `HTTPException`에 직접 쓴 `detail` 문구는 `details.detail`로 보존하고 `message`는 사전의 한국어 문구를 사용. 표준 문구("Not Found" 등)는 노출하지 않음.
- 500 응답에는 예외 메시지나 스택을 포함하지 않고 서버 로그에만 요청 번호와 함께 기록.
- 429(요청 과다) 전용 클래스와 `retry_after` 필드는 속도 제한을 구현하는 Task에서 추가 (YAGNI).

## 비고
- 새 오류 종류는 `AppError`를 상속하고 `status_code`, `error`를 지정하면 됨. 메시지 사전에 항목을 추가하면 기본 문구가 생김. (예: `edit_conflict`)
- 다음 작업: T017 (Celery 앱과 Redis 연결). 이것으로 Base Infrastructure 중 백엔드는 T017만 남음.
