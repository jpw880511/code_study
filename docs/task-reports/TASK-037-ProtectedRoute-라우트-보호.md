# TASK-037. ProtectedRoute 라우트 보호

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
회원 전용 구역 앞의 경비실입니다. `frontend/src/components/auth/ProtectedRoute.tsx`는 스토어의 `status`에 따라 세 가지로 동작합니다.
- `unknown`: "로그인 상태를 확인하는 중..." (`role="status"`, `aria-live="polite"`)만 표시. 절대 리다이렉트하지 않음.
- `unauthenticated`: `<Navigate to="/login" replace state={{ from: location }} />`
- `authenticated`: `children`이 있으면 children, 없으면 `<Outlet />`.

`frontend/src/App.tsx` 연결:
- 보호됨: 대시보드 `/`, `/projects/...`, `/trash`, 404(`*`)
- 공개 유지: `/login`, `/register`, 개발용 `/dev/query-demo`, `/dev-test`
- 내비게이션 바(AppLayout)에 "로그아웃" 버튼 추가. 인증된 상태에서만 표시되며 `useAuth().logout`을 호출.
- `App`을 `AuthProvider`로 감쌈(TASK-038 참조).

## 변경 파일
- `frontend/src/components/auth/ProtectedRoute.tsx` (신규)
- `frontend/src/App.tsx` (보호 라우트, 실제 로그인/회원가입 페이지, 로그아웃 버튼, AuthProvider)
- `frontend/tests/unit/ProtectedRoute.test.tsx` (신규, 5개)
- `frontend/tests/unit/App.test.tsx` (수정, 아래 참조)

## TDD 결과
- RED: ProtectedRoute 테스트와 App 테스트를 먼저 작성/수정 → 모듈 없음, 보호 동작 없음으로 13개 실패 확인
- GREEN: 구현 후 전체 251개 통과(기준선 147개에서 +104개)
- REFACTOR: Prettier/ESLint/`tsc`/빌드 통과, 전체 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 전체 문장 99.65%, 분기 98.24%(남은 분기는 이 Task와 무관한 기존 `ui/card.tsx`, `dialog.tsx`, dev 컴포넌트)
- 검증 범위: unknown 로딩/무리다이렉트, 미인증 리다이렉트와 `from`(쿼리 포함), children/Outlet 렌더, 상태 변화 반응, App 수준(공개 페이지, 로그인 상태 방문자 리다이렉트, dev 페이지 공개, 보호 라우트 5종 리다이렉트, unknown 로딩, 로그인 후 원래 페이지 복귀, 로그아웃 버튼 표시 조건과 동작, 시작 시 `/auth/me` 확인)

## 기술 결정
- **App.test.tsx를 같은 의도로 갱신.** 기존 테스트는 보호가 없는 자리표시자를 가정했으므로, 대시보드/휴지통/프로젝트/404/내비게이션 테스트는 먼저 스토어를 인증 상태로 만들고, 로그인/회원가입 테스트는 미인증 상태에서 실행합니다. 단언은 삭제하거나 약화하지 않았고(`/login`, `/register`에서 내비게이션이 숨겨지는 것 포함) 새 동작 테스트를 추가했습니다. dev 라우트 테스트는 `QueryClientProvider`로 감쌈.
- dev 라우트는 AppLayout 안에 두되 ProtectedRoute 밖에 두어 공개로 유지. 404는 보호 안에 있어 미인증이면 로그인으로 갑니다.
- `AppRoutes`는 순수하게 유지(부트스트랩 없음)해 테스트가 스토어 상태만으로 라우팅을 검증할 수 있게 했습니다.

## 비고
- 새로고침 시: 처음엔 `unknown` → 로딩 표시 → `/auth/me` 결과에 따라 화면 또는 로그인 이동.
