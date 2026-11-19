# TASK-038. 자동 토큰 갱신 (useAuth)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
출입증 자동 갱신 담당자입니다. 토큰은 HttpOnly 쿠키라 JS가 만료를 볼 수 없으므로 "주기적으로 갱신"과 "만료 오류를 만나면 갱신 후 재시도" 두 가지를 함께 씁니다.
- (a) 시작 시 확인: status가 `unknown`이면 `GET /auth/me`. 성공 → `setUser`. 401 `session_expired` → `POST /auth/refresh` 한 번 → `me` 재시도. 그 외 모든 실패(네트워크 포함) → `clearUser`(`unknown`에 갇히지 않음).
- (b) 선제 갱신: 인증된 동안 10분마다 `POST /auth/refresh`. 실패 시 `clearUser`. 로그아웃/언마운트 시 타이머 정리.
- (c) 사후 갱신: 다른 요청이 401 `session_expired`로 실패하면 단일 비행(single-flight) 갱신 1회(동시 실패는 같은 호출을 공유) 후 원래 요청을 한 번만 재시도. 갱신 실패 시 `clearUser`하고 원래 오류를 전달. `/auth/*` 요청은 대상에서 제외(루프 방지).
- (d) `useAuth()`: `user`, `status`, `isAuthenticated`, `login`(서버 호출 후 `setUser`), `register`(스토어 변경 없음), `logout`(서버가 실패해도 항상 `clearUser`, 오류는 삼킴).

## 변경 파일
- `frontend/src/hooks/useAuth.ts` (신규, `useAuth`, `useAuthBootstrap`, `REFRESH_INTERVAL_MS`)
- `frontend/src/services/session.ts` (신규, `refreshSession`, `installSessionRefresh`, `bootstrapSession`)
- `frontend/src/components/auth/AuthProvider.tsx` (신규)
- `frontend/src/services/api-client.ts` (`ApiError`에 실패한 요청의 `config` 필드 추가)
- `frontend/tests/unit/session.test.ts` (신규, 16개), `frontend/tests/unit/useAuth.test.tsx` (신규, 23개)

## TDD 결과
- RED: session/useAuth 테스트를 먼저 작성 → 모듈 없음으로 실패 확인. (`bootstrapSession`은 `session.ts`를 쓸 때 함께 작성했고, 그 동작은 이후 useAuth 테스트로 검증함)
- GREEN: session 16개, useAuth 23개 통과
- REFACTOR: 갱신 로직을 훅에서 `session.ts`로 분리(순수 서비스 + 얇은 훅), Prettier/ESLint/빌드 통과 후 전체 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: hooks/useAuth.ts, services/session.ts, auth-service.ts 문장/분기 100%
- 검증 범위: 단일 비행 공유/재시작/실패 후 재시도 허용, 동시 3건 401에 갱신 1회, 원 요청 1회 재시도(POST 본문 유지), 재실패 시 루프 없음, 갱신 실패 시 스토어 비움과 원래 오류 전달, `/auth/*`·401 `not_authenticated`·403·500은 무시, interceptor 제거, 시작 확인 6가지 경로 + StrictMode 중복 실행 시 1회, 가짜 타이머로 10분 주기/실패/언마운트/로그아웃/로그인 후 시작, 로그인/가입/로그아웃 동작

## 기술 결정
- **부트스트랩 위치: `AuthProvider`(App 최상단, `BrowserRouter` 바깥).** 라우트와 무관하게 앱 수명 동안 한 번만 마운트되고, `AppRoutes`는 순수하게 남아 테스트가 쉽습니다. `useAuthBootstrap`을 각 페이지에서 호출하면 중복 위험이 있어 한 곳으로 고정했습니다.
- **재시도를 위해 `ApiError.config` 추가.** 응답 interceptor는 `api-client`의 변환 interceptor 뒤에 실행되어 원래 axios 오류가 아니라 `ApiError`를 받습니다. 요청을 다시 보내려면 원 요청 정보가 필요해서 `ApiError`에 `config`를 담았습니다(기존 동작/필드 불변). 재시도 표시는 요청 config의 `_sessionRetried`로 하여 두 번째 만료 오류가 루프를 만들지 않습니다.
- **부트스트랩은 `bootstrapSession` 단일 비행**: React StrictMode가 effect를 두 번 실행해도 `/auth/me`는 한 번만 호출됩니다.
- **갱신 호출을 공유**: 선제 타이머, 사후 갱신, 시작 시 갱신이 모두 `refreshSession` 하나를 써서 동시 호출이 겹치지 않습니다.
- `logout`은 서버 실패를 삼킵니다. 사용자 입장에서 로컬 상태는 반드시 로그아웃되어야 하고 쿠키는 만료로 정리되기 때문입니다.
- 인터셉터는 효과(effect)에서 설치/제거하므로 테스트마다 격리되고, `AuthProvider`가 없는 곳(단위 테스트)에는 영향을 주지 않습니다.

## 비고
- 백엔드 없이 가짜 어댑터로만 검증했습니다. 수동 테스트(T039~T042)에서 확인할 것: 로그인 직후 새로고침 시 로그인 유지, 쿠키가 만료된 상태에서 `/auth/me`가 `session_expired`를 주면 갱신되는지, 15분 경과 후 요청 동작, 로그아웃 후 보호 페이지 접근 시 로그인 이동. 서버의 `session_expired` 코드가 액세스 토큰 만료에만 쓰이고 리프레시 만료는 `not_authenticated`/`session_expired`로 `/auth/refresh`에서만 나온다는 계약을 전제로 합니다.
- 서버 CORS는 `withCredentials`를 허용해야 하며(origin 명시), 쿠키 SameSite 설정이 개발 환경(localhost:5173 → localhost:8000)에서 전송되도록 해야 합니다.
