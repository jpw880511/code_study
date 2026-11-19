# TASK-031. POST /auth/refresh 엔드포인트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`POST /api/v1/auth/refresh`: `refresh_token` 쿠키로 `TokenService.rotate_refresh_token` 호출. 성공 시 **204**(본문 없음)와 새 쿠키 2개(로그인과 같은 속성). 이전 리프레시 토큰은 폐기되고 새 것이 저장되며, 이전 것을 다시 쓰면 401. 실패(쿠키 없음, 쓰레기, 모르는 토큰, 폐기됨, 액세스 토큰을 넣음)는 401 `not_authenticated`, 리프레시 토큰이 만료되었으면 401 `session_expired`이며 **같은 응답에서 두 쿠키를 비움**. 실패 시 DB 변화 없음.

## 변경 파일
- `backend/src/api/auth.py` (신규, `auth_router`), `backend/src/api/router.py` (라우터 등록)
- `backend/tests/integration/test_auth_api_db.py` (신규, T028~T031 공용 테스트 61개 중 해당 부분)

## TDD 결과
- RED/GREEN: 테스트 먼저 작성 → 실패 확인 → 구현 후 통과. 회전 후 DB 상태(옛 것 revoked, 새 것 저장)와 commit 여부를 별도 세션으로 확인
- 전체 흐름 테스트(register → login → me → refresh → me → logout → refresh 실패, 쿠키 저장소 사용) 통과
- 전체 404개 통과, 건너뜀 0, `src/` 커버리지 100%
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- REFACTOR: Ruff, Black, MyPy(strict) 통과

## 기술 결정
- 실패 응답을 예외로 던지지 않고 라우터가 직접 만들어 반환: 예외 처리기는 쿠키를 지울 수 없기 때문. 상태 번호는 `AUTH_ERROR_STATUS` 재사용.
- 실패 경로는 DB를 바꾸지 않으므로 이후 commit은 무해.
- 프런트엔드 참고: 401 + 쿠키 삭제 응답이면 로그아웃 상태로 전환. 동시에 여러 탭이 같은 토큰으로 갱신하면 한 쪽만 성공(서비스 설계).

## 비고
- CSRF는 `SameSite=Strict` 쿠키와 CORS 허용 목록에 의존(CSRF 토큰, 속도 제한, 비밀번호 변경, 이메일 인증은 범위 밖).
- 토큰은 어떤 응답 본문에도 포함되지 않음.
