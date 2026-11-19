# TASK-035. Register 페이지

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
접수 창구 화면입니다. `frontend/src/pages/Register.tsx`는 h1 "회원가입", `RegisterForm`, 로그인 링크를 보여 줍니다.
- 가입 성공 시 로그인하지 않고(서버가 쿠키를 주지 않음) `/login`으로 이동하며 라우터 state `{ registered: true }`를 넘깁니다. 로그인 페이지는 이 state로 "회원가입이 완료되었습니다. 로그인하세요." 안내를 표시.
- 이미 로그인된 방문자는 `/`로 리다이렉트.
- 서버 오류(예: 409 이미 가입된 이메일)는 폼의 alert에 표시되고 페이지에 머묾.

## 변경 파일
- `frontend/src/pages/Register.tsx` (신규)
- `frontend/src/App.tsx` (자리표시자 페이지를 실제 페이지로 교체, TASK-037 참조)
- `frontend/tests/unit/auth-pages.test.tsx` (신규, Login 페이지 테스트와 함께)

## TDD 결과
- RED: 테스트 먼저 작성 → 페이지 모듈 없음으로 실패 확인
- GREEN: Register 케이스 5개 통과
- REFACTOR: Prettier 정리 후 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: Register.tsx 100%
- 검증 범위: h1과 링크, 성공 후 로그인 페이지 이동 + 안내 + 스토어 미변경 + 요청 확인, 서버 오류 표시, 로그인 상태 방문자 리다이렉트

## 기술 결정
- 가입 후 자동 로그인을 하지 않음: 계약상 register는 쿠키를 설정하지 않으며, 사용자가 계정 생성을 확인하도록 로그인 화면을 거칩니다.
- 안내 문구는 URL 쿼리 대신 라우터 state로 전달해 새로고침하면 사라집니다(일회성 안내).
- status가 `unknown`인 동안에는 리다이렉트하지 않고 폼을 그대로 보여 줍니다(부트스트랩이 끝나면 필요 시 이동).

## 비고
- 로그인/회원가입 페이지는 내비게이션 바가 없는 공개 라우트입니다.
