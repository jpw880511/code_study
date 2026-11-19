# TASK-026. TokenService (토큰 발급, 검증, 순환)

## 상태
완료

## 날짜
2026-11-06

## 작업 요약
놀이공원의 "입장권 발급소"입니다. 로그인한 사람에게 두 종류의 표를 주고(짧은 입장권 + 갱신권), 입구에서 표를 확인하고, 갱신권을 새 표로 바꿔 줍니다. `backend/src/services/auth/token_service.py`의 `TokenService(session)`는 다음을 합니다.
- **`issue_tokens(user_id)`**: 액세스 토큰(15분)과 리프레시 토큰(7일)을 만들고, 리프레시 토큰은 **해시만** `refresh_tokens` 표에 기록합니다. `TokenPair`(두 토큰과 각각의 만료 시각)를 돌려주므로, API 계층이 쿠키 유효 기간을 정할 수 있습니다.
- **`verify_access_token(token)`**: 액세스 토큰이 유효한지 확인합니다. DB를 쓰지 않아 인스턴스 없이 `TokenService.verify_access_token(...)`으로 호출할 수 있습니다(T027의 인증 의존성이 요청마다 세션을 열지 않아도 되게).
- **`rotate_refresh_token(refresh_token)`**: 갱신권을 새 표 한 쌍으로 교환합니다. 이전 갱신권은 폐기되어 다시 쓸 수 없습니다("사용할 때마다 새로 발급, 이전 것 폐기"라는 research.md 방침).
- 오류 두 종류 추가(`errors.py`): `NotAuthenticatedError`(`로그인이 필요합니다.`)와 `SessionExpiredError`(`세션이 만료되었습니다. 다시 로그인하세요.`). 문구는 requirements-addendum의 401 메시지 그대로.

## 변경 파일
- `backend/src/services/auth/token_service.py` (신규), `backend/src/services/auth/errors.py` (오류 2종 추가)
- `backend/tests/unit/test_token_service.py`, `backend/tests/integration/test_token_service_db.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T026 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 서비스 모듈이 없어 수집 단계에서 실패 확인
- GREEN: 구현 후 첫 실행에서 전체 통과
- REFACTOR: 테스트의 긴 줄 정리, Ruff/Black/MyPy(strict) 통과. 전체 318개 통과, 건너뜀 0
- **변이 검사**: 행 잠금(`with_for_update`)을 일부러 제거하면 동시 순환 테스트가 "승자 2명"으로 실패하고, 복원하면 통과함을 확인(테스트가 실제로 동시성 오류를 잡아낼 수 있음을 증명)
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 범위
  - 발급: 두 토큰이 동작, 수명 15분/7일, 해시만 저장(원본은 어느 열에도 없음), 호출마다 새 토큰과 새 행, 없는 사용자는 거부
  - 액세스 토큰 검증: 유효/만료(`SessionExpiredError`)/쓰레기/변조/다른 비밀키/서명 없는 토큰/리프레시 토큰 혼용 거부, 오류 메시지에 토큰이 없음
  - 순환: 새 쌍 발급과 이전 것 폐기, 연속 순환, 재사용 거부, 다른 기기의 토큰 유지, 로그아웃(T025)된 토큰 거부, 서명만 맞고 기록에 없는 토큰 거부, 만료(JWT 만료와 DB 만료 모두), 토큰의 사용자와 기록의 사용자가 다르면 거부, 사용자 ID가 아닌 subject 거부, 삭제된 사용자의 토큰 거부, 실패한 순환은 아무것도 바꾸지 않음
  - 실제 동시성: 두 연결로 같은 갱신권을 동시에 교환하면 **정확히 한 쪽만 성공**하고 살아 있는 토큰은 1개

## 기술 결정
- **교환 중 행 잠금(`SELECT ... FOR UPDATE`).** 프런트엔드의 자동 갱신(T038)이 같은 갱신권으로 거의 동시에 두 번 요청할 수 있습니다. 잠금이 없으면 둘 다 성공해 새 토큰이 두 쌍 생깁니다. 잠금이 있으면 뒤 요청이 기다렸다가 "이미 폐기됨"을 보고 거부됩니다.
- **재사용 감지 시 전체 로그아웃은 하지 않음.** 이미 쓴 갱신권이 다시 오면 그 요청만 거부하고, 사용자의 새 토큰은 폐기하지 않습니다. 탈취 대응으로 "전부 폐기"하는 방식도 있지만 설계서에 없고, 브라우저 탭 두 개가 동시에 갱신하는 정상적인 상황에서 사용자를 모든 기기에서 로그아웃시키는 부작용이 큽니다(테스트로 고정). 보안 요구가 커지면 별도 Task로 검토.
- **서명이 맞아도 기록에 있어야 함.** 갱신권은 JWT 서명 검사 후에도 DB에 해시가 있고 폐기되지 않았으며 만료되지 않았고, 토큰의 사용자와 기록의 사용자가 일치해야 통과합니다.
- **만료는 두 군데에서 확인.** JWT의 `exp`와 DB의 `expires_at`. 만료는 "세션이 만료되었습니다"(`session_expired`), 그 외의 모든 실패는 "로그인이 필요합니다"(`not_authenticated`)로 구분해 프런트엔드가 안내를 다르게 할 수 있게 함.
- **DB 만료 시각을 JWT에서 다시 읽어 저장.** 발급 직후 토큰을 해석해 만료 시각을 얻으므로 JWT와 DB 값이 어긋날 수 없음.
- `revoked`가 NULL인 행도 폐기되지 않은 것으로 취급(T024 비고의 약속).
- 로그아웃은 T025의 `UserService.logout`에 그대로 두었습니다. 폐기 로직(두 줄)이 한 곳 더 있지만, 서비스끼리 직접 호출하지 않는다는 방침(헌법)을 지키기 위해 중복을 감수함.
- 서비스는 커밋하지 않고 flush만 합니다. 커밋은 요청의 세션이 담당.

## 비고
- T028~T031(인증 API)에서 이 서비스를 사용: 로그인은 `UserService.login` 후 `issue_tokens`, 갱신은 `rotate_refresh_token`, 쿠키 설정은 `TokenPair`의 만료 시각 이용. `NotAuthenticatedError`/`SessionExpiredError`는 401로, T025의 오류들과 함께 한 곳에서 응답으로 변환.
- 모든 비밀번호 변경 시 전체 폐기(`revoke all`)는 비밀번호 변경 기능에서 구현. 지금은 필요한 사용처가 없어 만들지 않음.
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`이 `.env`에 없으면 `TokenService(session)`을 만드는 순간 오류가 납니다(T012의 설정). 실서버 실행 전에 두 값을 32자 이상으로 채워야 함.
- 다음 작업: T027 (인증 의존성).
