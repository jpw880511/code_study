# TASK-029. POST /auth/login 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`POST /api/v1/auth/login`: `UserService.login` 후 같은 트랜잭션에서 `TokenService.issue_tokens` → **200** `UserResponse` + 쿠키 2개. `access_token`(Path=/, Max-Age≈900), `refresh_token`(Path=/api/v1/auth, Max-Age≈604800), 둘 다 HttpOnly, SameSite=Strict, `Secure`는 `environment == "production"`일 때만. 토큰은 본문에 없음. 잘못된 비밀번호/없는 이메일/잘못된 이메일 형식은 모두 같은 401 `invalid_credentials` 본문이며 쿠키 없음. 실패 시 refresh_tokens 행도 생기지 않음.

## 변경 파일
- `backend/src/api/cookies.py` (신규: `set_auth_cookies`, `clear_auth_cookies`, `seconds_until`)
- `backend/src/api/dependencies.py` (`REFRESH_TOKEN_COOKIE`, `REFRESH_COOKIE_PATH`)
- `backend/tests/unit/test_auth_cookies.py` (신규)
- `backend/src/api/auth.py` (신규, `auth_router`), `backend/src/api/router.py` (라우터 등록)
- `backend/tests/integration/test_auth_api_db.py` (신규, T028~T031 공용 테스트 61개 중 해당 부분)

## TDD 결과
- RED: 로그인 테스트 포함 파일이 수집 단계에서 실패
- **발견한 문제(RED):** `get_session`의 commit이 응답이 전송된 *후*에 실행되고 있었음(FastAPI 0.162 기본 동작). "응답 시작 시점에 다른 세션에서 사용자가 보이는가" 테스트가 실패(`[False]`)하여 확인
- GREEN: `DbSession = Depends(get_session, scope="function")`로 변경 → commit이 엔드포인트 종료 직후, 응답 전송 전에 실행. 통과
- 로그인 후 `last_login_at`과 해시만 저장된 refresh_tokens 행이 실제 commit되었음을 별도 세션으로 확인
- 전체 404개 통과, 건너뜀 0, `src/` 커버리지 100%
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- REFACTOR: Ruff, Black, MyPy(strict) 통과

## 기술 결정
- **commit 시점 수정(중요):** 기존 `get_session`은 yield 이후 commit하므로 FastAPI 0.118+에서는 응답 전송 후에 실행됩니다. 클라이언트가 201/200을 받고 곧바로 다음 요청을 하면 데이터가 아직 없을 수 있고, commit 실패도 성공 응답 뒤에 숨습니다. 의존성 선언에서 `scope="function"`을 지정해 해결(`get_session` 자체와 `get_current_user`도 이 별칭 사용). 이후 DB를 바꾸는 모든 엔드포인트는 `DbSession`을 써야 합니다.
- `Secure` 플래그는 `app.state.settings.environment`로 판단(`create_app(settings)`가 하나의 출처).
- 로그인 응답에서 이메일 존재 여부가 드러나지 않음(서비스의 더미 해시 검증 유지).

## 비고
- CSRF는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존(CSRF 토큰, 속도 제한, 비밀번호 변경, 이메일 인증은 범위 밖).
- 토큰은 어떤 응답 본문에도 포함되지 않음.
