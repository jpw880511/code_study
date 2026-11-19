# TASK-021. Zustand 인증 스토어

## 상태
완료

## 날짜
2026-11-04

## 작업 요약
건물 입구의 "출입 확인판"과 같습니다. 지금 들어와 있는 사람이 누구인지, 아직 확인 중인지를 한곳에 적어 두고 모든 화면이 같은 판을 봅니다. `frontend/src/stores/auth-store.ts`에 다음을 구현했습니다.
- `useAuthStore`(Zustand): `user`(id, email, skill_level 또는 없음), `status`, 그리고 두 동작 `setUser(user)`(로그인됨), `clearUser()`(로그인 안 됨).
- `status`는 세 가지: `unknown`(서버에 아직 묻지 않음, 시작 상태), `authenticated`, `unauthenticated`.
- `selectIsAuthenticated`: 로그인 여부를 꺼내는 선택자.
- 화면 안에서는 `useAuthStore(selectIsAuthenticated)`로, 화면 밖(예: HTTP 인터셉터)에서는 `useAuthStore.getState()`로 쓸 수 있음.

## 변경 파일
- `frontend/src/stores/auth-store.ts` (신규)
- `frontend/tests/unit/auth-store.test.ts` (신규)
- `frontend/package.json` (`zustand` 5.0.16)
- `specs/001-ai-code-learning-platform/tasks.md` (T021 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈 없음으로 실패 확인
- GREEN: 구현 후 첫 실행에서 통과. 전체 103개(신규 13개)
- REFACTOR: Prettier/ESLint/`tsc`/빌드 통과 후 재실행 103개 유지
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 문장 100%, 분기 97.3% (남은 분기는 이 Task와 무관한 개발용 데모의 환경변수 분기)
- 검증 범위: 초기 상태, 로그인/로그아웃 전환, 사용자 교체, 선택자, 토큰 관련 이름이 상태에 없음, 브라우저 저장소에 아무것도 쓰지 않음, React 훅으로 구독 시 재렌더링, React 밖에서 갱신

## 기술 결정
- **토큰을 저장하지 않음.** research.md에 따라 JWT는 HTTP-only 쿠키로 오가고 JavaScript는 읽을 수 없습니다. 그래서 tasks.md의 "JWT state"를 "인증 상태(누가 로그인했는가)"로 해석했습니다. 토큰 이름이 상태에 없다는 것을 테스트로 고정했습니다.
- **`unknown` 상태를 둠.** 페이지를 새로 열면 서버에 `GET /auth/me`(T029A)로 물어보기 전까지는 로그인 여부를 알 수 없습니다. 이 상태가 없으면 T037의 ProtectedRoute가 새로고침할 때마다 로그인 화면으로 잠깐 보내게 됩니다.
- **저장소에 유지(persist)하지 않음.** 쿠키가 진실의 원천이므로 이메일 등 사용자 정보를 localStorage에 복사할 이유가 없고, 복사하면 오래된 정보가 남을 위험만 생깁니다. 새로고침 시에는 `/auth/me`로 다시 채웁니다. 테스트로 고정.
- 사용자 필드는 data-model.md의 이름을 그대로 써서(`skill_level`) API 응답과 변환 없이 맞춤. 서버 응답 형식은 T028~T029A에서 확정되므로 그때 필드가 더 필요하면 확장.
- 서버 호출(로그인/로그아웃/`me`)과 401 처리는 이 스토어에 넣지 않음. T034(auth-service), T038(useAuth)에서 이 스토어를 사용함.

## 비고
- 이 스토어는 아직 사용처가 없어 운영 번들에 포함되지 않음(트리 셰이킹, 번들 크기 변화 없음).
- 다음 작업: T022 (Tailwind CSS와 shadcn/ui). 이것으로 프론트엔드 기반(T018~T021)이 끝나고 T022만 남음.
