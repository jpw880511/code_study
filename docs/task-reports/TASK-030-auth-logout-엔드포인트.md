# TASK-030. POST /auth/logout 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`POST /api/v1/auth/logout`: 인증 의존성 없음(액세스 토큰이 만료되어도 동작). `refresh_token` 쿠키로 `UserService.logout` 호출 → 해당 토큰 하나만 폐기. 쿠키가 없거나 모르는/이미 폐기된 토큰이어도 항상 **204**(멱등)이며 두 쿠키를 같은 이름과 같은 Path로 비움(빈 값, Max-Age=0, HttpOnly, SameSite=Strict, production이면 Secure). 다른 기기의 토큰은 그대로이고, 로그아웃한 토큰으로 갱신하면 401.

## 변경 파일
- `backend/src/api/auth.py` (신규, `auth_router`), `backend/src/api/router.py` (라우터 등록)
- `backend/tests/integration/test_auth_api_db.py` (신규, T028~T031 공용 테스트 61개 중 해당 부분)

## TDD 결과
- RED/GREEN: 테스트 먼저(만료된 액세스 쿠키 + 유효 리프레시, 쿠키 없음/쓰레기/빈 값/모르는 토큰, 두 번 호출, 다른 기기 토큰 유지) → 실패 확인 후 구현, 통과
- 별도 세션으로 폐기가 실제 commit되었음을 확인
- 전체 404개 통과, 건너뜀 0, `src/` 커버리지 100%
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- REFACTOR: Ruff, Black, MyPy(strict) 통과

## 기술 결정
- 항상 204: 로그아웃 요청이 오류를 내면 사용자가 로그아웃되지 않은 것처럼 보이므로 클라이언트가 항상 쿠키를 정리할 수 있게 함.
- CSRF: 이번 범위 밖. 현재는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존. 이중 제출 토큰은 이후 과제.

## 비고
- CSRF는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존(CSRF 토큰, 속도 제한, 비밀번호 변경, 이메일 인증은 범위 밖).
- 토큰은 어떤 응답 본문에도 포함되지 않음.
