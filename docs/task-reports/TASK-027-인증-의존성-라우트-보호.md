# TASK-027. 인증 의존성 (라우트 보호)

## 상태
완료

## 날짜
2026-11-06

## 작업 요약
건물 입구의 "출입증 검사원"입니다. 보호할 API에 검사원을 세워 두면, 출입증(액세스 토큰 쿠키)이 없거나 만료되었거나 가짜이면 안으로 들여보내지 않고, 정상이면 "누가 왔는지"를 돌려줍니다. `backend/src/api/dependencies.py`에 다음을 만들었습니다.
- `get_current_user_id`: 쿠키 `access_token`의 JWT만 확인해 사용자 id를 돌려줍니다(DB 조회 없음). 쓰는 쪽에서는 `CurrentUserId` 타입으로 받습니다.
- `get_current_user`: 위 id로 DB에서 `User`를 읽어 돌려줍니다. 쓰는 쪽에서는 `CurrentUser` 타입으로 받습니다.
- 사용법: `async def handler(user: CurrentUser): ...` 처럼 매개변수 타입만 적으면 그 엔드포인트가 보호됩니다.
- 실패 응답은 모두 401 + 기존 오류 형식(`{"error", "message"}`)이며, 쿠키가 없거나 가짜이면 `not_authenticated`("로그인이 필요합니다."), 만료되었으면 `session_expired`("세션이 만료되었습니다. 다시 로그인하세요.")입니다. 프런트엔드는 만료일 때 `/auth/refresh`를 호출할 수 있습니다.
- **`AuthError` → HTTP 응답 변환기를 `api/exceptions.py`에 추가.** T025/T026의 업무 오류(서비스 계층)가 응답이 되는 길입니다. 이것이 없으면 보호된 경로가 401이 아니라 500을 냅니다. T028~T031의 인증 API도 이것을 그대로 사용합니다.

| 오류 코드 | HTTP 상태 |
|---|---|
| `not_authenticated`, `session_expired`, `invalid_credentials` | 401 |
| `email_already_registered` | 409 |
| `invalid_email`, `weak_password` | 422 |
| 목록에 없는 `AuthError` | 400 (서버 오류로 처리하지 않음) |

## 변경 파일
- `backend/src/api/dependencies.py` (신규)
- `backend/src/api/exceptions.py` (`AuthError` 변환기와 상태 번호 표 추가)
- `backend/pyproject.toml` (커버리지 측정 설정, 아래 비고)
- `backend/tests/unit/test_auth_error_handler.py`, `backend/tests/integration/test_auth_dependencies_db.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T027 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈이 없어 수집 단계에서 실패, 변환기 테스트는 `AuthError`가 일반 500 처리기로 떨어지는 것을 확인
- GREEN: 구현 후 첫 실행에서 통과
- REFACTOR: 테스트의 httpx 쿠키 사용 방식을 권장 방식으로 정리(경고 15건 제거), 커버리지 설정 보강. Ruff/Black/MyPy(strict) 통과. 전체 343개 통과, 건너뜀 0
- **변이 검사:** "삭제된 사용자" 분기를 일부러 바꾸면 해당 테스트 2개가 정확히 실패하고 복원하면 통과함을 확인
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 범위: 정상 쿠키로 사용자 반환, 요청마다 다른 사용자, 쿠키 없음/빈 쿠키, 만료, 쓰레기 값, 리프레시 토큰을 액세스 자리에 넣기, 다른 비밀키로 서명한 토큰, 존재하지 않는 사용자, 사용 중 삭제된 사용자의 즉시 차단, 사용자 id가 아닌 subject, `Authorization: Bearer` 헤더는 받아들이지 않음, 보호되지 않은 경로는 쿠키 없이 동작, 거부 응답에도 요청 번호 헤더가 붙음, 각 `AuthError` 코드의 상태 번호와 본문

## 기술 결정
- **쿠키만 인정하고 `Authorization` 헤더는 받지 않음.** research.md는 JWT를 HTTP-only 쿠키로 정했고, 헤더까지 받으면 인증 경로가 둘이 되어 점검할 곳이 늘어납니다. 테스트로 고정. (API 문서 화면에서도 로그인 후 같은 도메인의 쿠키로 시험 가능)
- **두 단계로 분리.** 대부분의 엔드포인트는 "누구의 데이터인가"(user_id)만 필요해서 DB를 읽지 않는 `CurrentUserId`를 따로 두었습니다. 사용자 정보 자체가 필요한 곳(예: `/auth/me`)은 `CurrentUser`를 씁니다. `CurrentUser`는 매번 DB에서 읽으므로, 탈퇴/삭제된 사용자의 토큰은 만료 전이라도 바로 거부됩니다(`CurrentUserId`는 토큰 만료까지 통과하므로 용도를 구분해야 함).
- **JWT 설정을 의존성으로 주입(`Depends(get_jwt_settings)`).** 테스트에서 비밀키를 바꿔 끼우기 쉽고, 환경변수가 없으면 요청 시점에 명확한 오류가 납니다.
- **검증 오류의 HTTP 상태는 422.** 기존 요청 검증 오류(T016)가 422이므로 `invalid_email`, `weak_password`도 맞춤. requirements-addendum은 검증 오류를 400으로 적었으나 앱 내 일관성을 우선했습니다. 한 줄(`AUTH_ERROR_STATUS`)로 바꿀 수 있음.
- 서비스 계층 오류를 변환하는 코드는 API 계층에 둠(API → 서비스 방향 유지).
- 보호된 읽기 요청도 `get_session` 의존성이 요청 끝에 commit을 호출하지만, 변경이 없으므로 영향 없음.

## 비고
- **커버리지 설정:** SQLAlchemy 비동기가 greenlet 위에서 돌아서, 설정 없이는 `await` 뒤의 줄이 측정에서 빠지는 경우가 있었습니다(분기는 실제로 실행됨을 변이 검사로 확인). `pyproject.toml`에 `concurrency = ["greenlet", "thread"]`를 추가하니 100%로 정확히 측정됩니다.
- CSRF: 쿠키 인증이므로 상태를 바꾸는 요청의 CSRF 방어(`SameSite=Strict` 쿠키와 이중 제출 쿠키, research.md)는 쿠키를 실제로 설정하는 로그인 엔드포인트(T029)에서 함께 구현해야 함.
- 쿠키 이름 `access_token`은 `dependencies.py`의 상수. 로그인/갱신 엔드포인트가 같은 상수를 써서 쿠키를 설정해야 함(리프레시 쿠키 이름은 T029에서 정함).
- 다음 작업: T028 (회원가입 엔드포인트), T029 (로그인), T029A (`/auth/me`), T030 (로그아웃), T031 (토큰 갱신).
