# TASK-036. Login 페이지

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`frontend/src/pages/Login.tsx`: h1 "로그인", `LoginForm`, 회원가입 링크. 가입 직후라면 "회원가입이 완료되었습니다. 로그인하세요." 안내(`role="status"`)를 보여 줍니다.
- 로그인 성공 시 `useAuth().login`이 서버 호출 후 `useAuthStore.setUser`로 사용자를 저장합니다.
- 이후 사용자가 원래 가려던 곳(`location.state.from`) 또는 `/`로 이동합니다.
- 이미 로그인된 방문자는 같은 규칙으로 바로 이동합니다.
- 실패하면 서버 메시지를 alert로 보여 주고 스토어는 바뀌지 않습니다.

## 변경 파일
- `frontend/src/pages/Login.tsx` (신규)
- `frontend/src/App.tsx` (TASK-037 참조)
- `frontend/tests/unit/auth-pages.test.tsx` (신규, Register 테스트와 함께 12개)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈 없음으로 실패 확인
- GREEN: Login 케이스 7개 통과
- REFACTOR: Prettier 정리 후 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: Login.tsx 100%
- 검증 범위: h1과 링크, 안내 표시/미표시, 성공 후 스토어 저장과 `/` 이동, `from`(경로+쿼리) 복귀, 실패 시 alert와 스토어 불변, 로그인 상태 방문자 리다이렉트, status가 unknown일 때 폼 유지

## 기술 결정
- **이동을 한 곳에서 처리.** 로그인이 성공하면 `isAuthenticated`가 바뀌고, 그때 렌더되는 `<Navigate to={from ?? '/'}>`가 이동을 수행합니다. "이미 로그인된 방문자 리다이렉트"와 "로그인 성공 후 이동"이 같은 코드를 쓰므로, 별도 `navigate()` 호출과 경쟁(두 번 이동, `/`로 먼저 튕김)하는 문제가 없습니다.
- `from`은 ProtectedRoute가 넘긴 location 객체(경로+쿼리+해시)를 그대로 `to`로 사용해 쿼리 문자열도 복원됩니다.
- 비밀번호/토큰은 어디에도 저장하지 않습니다(브라우저 저장소 미사용).

## 비고
- 로그아웃 버튼으로 로그아웃하면 ProtectedRoute가 `from`을 현재 페이지로 붙여 `/login`으로 보내므로, 같은 계정/다른 계정으로 다시 로그인하면 그 페이지로 돌아옵니다. 필요하면 이후 작업에서 조정.
