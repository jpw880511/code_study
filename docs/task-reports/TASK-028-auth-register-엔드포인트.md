# TASK-028. POST /auth/register 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`POST /api/v1/auth/register`: 본문 `{"email","password"}` → `UserService.register` 호출 → **201** `{"id","email","skill_level"}`. 로그인은 하지 않으며 쿠키도 설정하지 않습니다. 중복 이메일(대소문자 무관) 409 `email_already_registered`, 형식 오류 422 `invalid_email`, 약한 비밀번호 422 `weak_password`, 필드 누락/타입 오류 422 `validation_error`. 응답 모델 `UserResponse`(`api/schemas.py`)는 세 필드만 가지므로 `password_hash`는 구조상 노출될 수 없습니다.

## 변경 파일
- `backend/src/api/schemas.py` (신규: `Credentials`, `UserResponse`)
- `backend/src/api/dependencies.py` (`DbSession` 별칭, `get_app_settings`, 쿠키 상수), `backend/src/main.py` (`app.state.settings`)
- `backend/src/api/auth.py` (신규, `auth_router`), `backend/src/api/router.py` (라우터 등록)
- `backend/tests/integration/test_auth_api_db.py` (신규, T028~T031 공용 테스트 61개 중 해당 부분)

## TDD 결과
- RED: 테스트 먼저 작성 → `REFRESH_TOKEN_COOKIE` 등이 없어 수집 단계 ImportError
- GREEN: 구현 후 61개 중 60개 통과, 1개(커밋 시점 테스트)는 실패 → TASK-029 참조
- 커밋 증명 테스트: 실제 `get_session`으로 등록 후 별도 세션에서 사용자와 bcrypt 해시 확인
- 전체 404개 통과, 건너뜀 0, `src/` 커버리지 100%
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- REFACTOR: Ruff, Black, MyPy(strict) 통과

## 기술 결정
- 서비스가 `register` 후 `skill_level`(서버 기본값)을 읽을 수 있어야 하므로 응답에 그대로 사용(테스트로 `Complete Beginner` 확인).
- 요청 필드는 `str`로 두고 형식/규칙 검사는 서비스에 맡김(규칙 한 곳).
- 쿠키 설정 로직은 `api/cookies.py`에 모아 로그인/갱신/로그아웃이 공유.

## 비고
- CSRF는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존(CSRF 토큰, 속도 제한, 비밀번호 변경, 이메일 인증은 범위 밖).
- 토큰은 어떤 응답 본문에도 포함되지 않음.
