# TASK-025. UserService (회원가입, 로그인, 로그아웃)

## 상태
완료

## 날짜
2026-11-05

## 작업 요약
건물 1층 "접수 창구"의 업무 규칙을 코드로 만든 작업입니다. `backend/src/services/auth/user_service.py`의 `UserService(session)`은 세 가지를 합니다.
- **`register(email, password)`**: 이메일을 정리(앞뒤 공백 제거, 소문자 통일)하고 형식을 검사한 뒤, 비밀번호 규칙을 검사하고 이미 가입된 이메일인지 확인한 다음 bcrypt 해시로 저장해 `User`를 돌려줍니다.
- **`login(email, password)`**: 자격이 맞으면 `User`를 돌려주고 `last_login_at`을 기록합니다. 어떤 이유로 실패해도 같은 오류(`이메일 또는 비밀번호가 올바르지 않습니다.`)만 냅니다.
- **`logout(refresh_token)`**: 이 기기의 리프레시 토큰 하나만 폐기(`revoked=True`, `revoked_at` 기록)합니다. 폐기할 것이 없으면 오류 없이 `False`.

함께 만든 것
- `errors.py`: HTTP와 무관한 업무 오류 4종(`InvalidEmailError`, `WeakPasswordError`, `EmailAlreadyRegisteredError`, `InvalidCredentialsError`). 각자 고정된 `code`와 한국어 기본 메시지를 가짐. API 계층(T028)이 이 `code`를 HTTP 응답으로 바꿉니다.
- `utils/security.py`에 `hash_refresh_token`(SHA-256 16진수 해시). 로그아웃과 곧 만들 TokenService(T026)가 같은 방식으로 해시하도록 공용으로 둠.
- 서비스는 커밋하지 않고 flush만 합니다. 커밋은 요청의 세션(`get_session`)이 합니다.

## 변경 파일
- `backend/src/services/__init__.py`, `backend/src/services/auth/__init__.py`, `errors.py`, `user_service.py` (신규)
- `backend/src/utils/security.py` (`hash_refresh_token` 추가)
- `backend/tests/unit/test_auth_validation.py`, `backend/tests/integration/test_user_service_db.py` (신규), `backend/tests/unit/test_security.py` (토큰 해시 테스트 추가)
- `specs/001-ai-code-learning-platform/tasks.md` (T025 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 서비스 모듈이 없어 수집 단계에서 실패 확인
- GREEN: 구현 후 첫 실행에서 전체 통과. (테스트 한 건은 제가 만든 한글 길이 예시가 틀려서 규칙이 아니라 테스트 문자열을 고침: 한글 23자는 70바이트라 제한 이내)
- REFACTOR: 긴 줄 정리, Ruff/Black/MyPy(strict) 통과. 전체 282개 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%
- 검증 범위
  - 순수 함수: 이메일 정리와 형식(경계 255자 포함), 비밀번호 규칙(길이, 문자+숫자, 72바이트, 바이트 기준 계산, 메시지에 비밀번호가 안 나옴), 오류 코드/메시지, 서비스가 API 계층에 의존하지 않음
  - 실제 PostgreSQL: 가입(정규화, 해시만 저장, 기본값, 이메일 중복은 대소문자 무관하게 거부, 잘못된 입력은 DB를 건드리지 않음, 동시 가입 경쟁에서 진 경우에도 세션이 계속 사용 가능), 로그인(대소문자와 공백 무시, 시각 기록, 실패 5종이 모두 같은 오류, 실패 시 마지막 로그인 시각 불변), 로그아웃(해당 토큰만 폐기, 모르는/빈 토큰은 오류 없음, 두 번 호출해도 첫 폐기 시각 유지, `revoked`가 NULL인 토큰도 폐기 가능)

## 기술 결정
- **이메일 소문자 통일은 서비스에서 처리.** T023 보고서에서 남겨 둔 숙제입니다. DB의 형식 검사는 대소문자를 구분하지 않지만 중복 검사는 구분하므로, 가입과 로그인 모두 같은 `normalize_email`을 거치게 했습니다.
- **로그인 실패는 모두 같은 오류, 같은 소요 시간.** 없는 이메일, 잘못된 형식, 틀린 비밀번호, 빈 비밀번호, 72바이트 초과를 구별할 수 없게 했습니다. 없는 이메일도 가짜 해시로 비밀번호 비교를 한 번 수행하여, 응답 시간으로 "가입된 이메일인지" 알아내는 것을 막습니다(테스트로 비교 1회 수행을 확인). 로그인 시 이메일 형식 오류를 따로 알려주지 않는 것도 같은 이유.
- **bcrypt는 이벤트 루프 밖(스레드)에서 실행.** 해시 1회에 약 0.3~0.4초가 걸려, 그대로 두면 그동안 서버가 다른 요청을 전혀 처리하지 못합니다. 해시하는 동안 다른 작업이 계속 돌아가는 것을 테스트로 확인.
- **업무 오류를 서비스 계층 안에 정의.** 기존 `AppError`는 API 계층에 있어서, 서비스가 그것을 쓰면 계층 방향(API → 서비스 → 모델)이 거꾸로 됩니다. 그래서 서비스는 자체 오류를 던지고, T028에서 `code`를 상태 번호로 연결합니다(예: `invalid_credentials`→401, `email_already_registered`→409, `weak_password`와 `invalid_email`→422 또는 400).
- **비밀번호 규칙:** 8자 이상, 문자와 숫자를 모두 포함, 72바이트 이하(bcrypt 한계, 한글은 24자). research.md에 "복잡도 규칙"이 있으나 내용이 정해져 있지 않아 최소한의 규칙으로 정함. 변경은 `validate_password` 한 곳.
- **로그아웃은 현재 기기의 토큰만.** requirements-addendum(CHK076)의 "로그아웃 시 현재 리프레시 토큰만 폐기"를 따름. 비밀번호 변경 시 전체 폐기는 비밀번호 변경 기능에서 구현.
- 가입은 먼저 중복을 조회하고, 동시 요청으로 뒤늦게 중복이 발생하면 세이브포인트로 감싼 저장에서 잡아 같은 오류로 바꿈(세션이 망가지지 않음).
- `last_login_at`은 DB 시각이 아니라 앱의 UTC 현재 시각으로 기록.

## 비고
- 아직 로그인에 성공해도 토큰은 발급되지 않습니다. 토큰 발급과 검증, 순환은 T026(TokenService)에서 만들고, T029의 로그인 엔드포인트가 `UserService.login`과 `TokenService`를 이어 붙입니다.
- 로그인 시도 횟수 제한(15분에 5회)과 계정 잠금은 요율 제한 기능에서 별도로 구현. 이 서비스에는 넣지 않음.
- 서비스는 호출하는 쪽의 로그(로그인 성공/실패 기록 등)를 남기지 않습니다. 보안 이벤트 로깅(CHK077)은 API 계층 또는 별도 Task에서.
- 다음 작업: T026 (TokenService), T027 (인증 의존성).
