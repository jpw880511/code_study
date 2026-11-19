# TASK-013. 비밀번호 해싱 유틸리티 (bcrypt)

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
비밀번호를 금고에 "원본 그대로" 보관하지 않고, 되돌릴 수 없는 지문(해시)으로만 저장하는 기능입니다. `backend/src/utils/security.py`에 두 함수를 만들었습니다.
- `hash_password(password)`: bcrypt(cost factor 12)로 해시 생성. 매번 다른 무작위 salt가 들어가 같은 비밀번호도 매번 다른 해시가 나옵니다.
- `verify_password(password, hash)`: 입력한 비밀번호가 저장된 해시와 맞는지 True/False로 반환. 해시가 손상됐거나 형식이 틀려도 예외 없이 False.

## 변경 파일
- `backend/src/utils/security.py` (신규)
- `backend/tests/unit/test_security.py` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T013 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → `src.utils.security` 없음으로 실패 확인
- GREEN: 구현 후 첫 실행에서 통과
- REFACTOR: Ruff/Black/MyPy(strict) 정리 후 전체 84개 테스트 통과, 건너뜀 0 (변경 사항 없음)
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (security.py 18문장)

## 기술 결정
- 비용 계수 12는 data-model.md/research.md 요구사항. 해시 1회에 약 0.4초가 걸려 무차별 대입 공격을 늦춤(테스트 시간도 이에 따라 늘어남).
- bcrypt는 72바이트 초과를 처리하지 못함. 조용히 잘라내면 비밀번호 뒷부분이 무시되는 보안 문제가 생기므로, 해시 생성 시에는 `ValueError`로 거부하고 검증 시에는 False를 반환. 글자 수가 아닌 UTF-8 바이트 기준이라 한글은 24자까지(글자당 3바이트).
- 빈 비밀번호는 해시 생성을 거부.
- 별도 라이브러리(passlib) 없이 `bcrypt` 직접 사용 (의존성 최소화).
- 비밀번호 규칙(최소 8자, 복잡도)과 72바이트 초과 시 사용자에게 보여줄 메시지는 인증 서비스/스키마 단계(이후 Task)에서 검증해야 함.

## 비고
- 다음 작업: T014 (FastAPI 앱 초기화, CORS, 미들웨어).
