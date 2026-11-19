# TASK-029A. GET /auth/me 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`GET /api/v1/auth/me`: `CurrentUser` 의존성으로 현재 사용자를 읽어 **200** `UserResponse`. 쿠키 없음/쓰레기 값 401 `not_authenticated`, 만료 401 `session_expired`. 프런트엔드가 새로고침 후 로그인 상태를 확인하는 데 사용.

## 변경 파일
- `backend/src/api/auth.py` (신규, `auth_router`), `backend/src/api/router.py` (라우터 등록)
- `backend/tests/integration/test_auth_api_db.py` (신규, T028~T031 공용 테스트 61개 중 해당 부분)

## TDD 결과
- RED/GREEN: TASK-028과 같은 테스트 파일에서 먼저 실패 확인 후 통과(쿠키 없음, 만료, 쓰레기 값, 올바른 쿠키 + 다른 사용자가 있어도 본인 반환)
- 전체 404개 통과, 건너뜀 0, `src/` 커버리지 100%
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- REFACTOR: Ruff, Black, MyPy(strict) 통과

## 기술 결정
- 비즈니스 로직 없이 T027 의존성을 그대로 사용. 응답은 `UserResponse`로 제한(비밀번호 해시 비노출).
- OpenAPI 문서에 5개 연산이 모두 등록됨을 테스트로 고정.

## 비고
- CSRF는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존(CSRF 토큰, 속도 제한, 비밀번호 변경, 이메일 인증은 범위 밖).
- 토큰은 어떤 응답 본문에도 포함되지 않음.
