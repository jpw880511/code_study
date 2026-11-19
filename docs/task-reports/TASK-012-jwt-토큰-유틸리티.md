# TASK-012. JWT 토큰 유틸리티 (생성, 검증, 해석)

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
놀이공원 입장권을 발급하고 입구에서 진짜인지, 기간이 지나지 않았는지 확인하는 기능입니다. `backend/src/utils/jwt.py`에 다음을 만들었습니다.
- `create_access_token` / `create_refresh_token`: 사용자 ID를 담은 토큰 발급 (접근용 15분, 갱신용 7일).
- `decode_token`: 서명, 만료, 토큰 종류를 확인하고 내용(`TokenPayload`)을 돌려줌. 실패하면 `ExpiredTokenError`(만료) 또는 `InvalidTokenError`(위조/형식 오류/종류 불일치).
- `verify_token`: 예외 없이 True/False만 반환.
- `JWTSettings`/`get_jwt_settings`: `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`(각각 32자 이상)과 만료 시간을 환경변수/`.env`에서 읽음.

## 변경 파일
- `backend/src/utils/__init__.py`, `backend/src/utils/jwt.py` (신규)
- `backend/tests/unit/test_jwt.py` (신규)
- `.env.example` (JWT 만료 설정 항목, 32자 안내 추가)
- `specs/001-ai-code-learning-platform/tasks.md` (T012 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.utils.jwt` 없음으로 실패 확인
- GREEN: 구현 후 설정 객체가 필드 이름(`secret_key=`)으로 생성되지 않는 문제(별칭 사용 때문)로 실패 → 구현에 `populate_by_name=True`를 추가해 통과 (테스트는 수정하지 않음. 타입 검사용 주석만 1줄 추가)
- REFACTOR: Ruff/Black/MyPy(strict) 정리 후 전체 66개 테스트 통과, 건너뜀 0
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (jwt.py 71문장)

## 기술 결정
- research.md 결정 반영: 접근 토큰 15분, 갱신 토큰 7일. 쿠키 설정은 인증 API 단계(이후 Task)에서 처리.
- 접근/갱신 토큰에 서로 다른 비밀키를 사용하고, 추가로 `type` 클레임도 검사하여 갱신 토큰을 접근 토큰으로 쓰는 것을 이중으로 차단.
- 알고리즘을 HS256으로 고정해서 해석 시 `algorithms=[...]`로 제한 → 서명 없는 토큰(alg=none) 공격 차단 (테스트로 검증).
- 필수 클레임: `sub`, `iat`, `exp`, `jti`. `jti`(토큰 고유 ID)는 갱신 토큰 회전/폐기(RefreshToken 테이블)에 쓰이도록 미리 포함.
- 비밀키 최소 32자 검증으로 약한 키를 시작 시점에 거부. `.env.example`의 자리표시자는 의도적으로 짧아서 교체 전에는 실행되지 않음.
- 시간 클레임은 UTC 초 단위로 맞춰 만료 길이를 정확히 계산 가능하게 함.

## 비고
- `.env`에 `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`을 32자 이상의 서로 다른 값으로 설정해야 인증 기능이 동작함. 생성 예: `openssl rand -hex 32`.
- 다음 작업: T013 (비밀번호 해싱 bcrypt).
