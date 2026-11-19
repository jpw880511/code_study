# TASK-018. React Router 라우트 구조 설정

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
건물 안내도를 먼저 그려 두는 작업입니다. 어떤 주소로 들어가면 어떤 "방(페이지)"이 나오는지를 정하고, 방은 아직 비워 둔 채(자리표시 페이지) 길만 연결했습니다. 이후 Task에서 각 방을 실제 화면으로 채우면 됩니다. `frontend/src/App.tsx`에 다음을 구현했습니다.

| 주소 | 페이지 | 내비게이션 바 |
|---|---|---|
| `/login` | 로그인 | 없음 |
| `/register` | 회원가입 | 없음 |
| `/` | 대시보드 (프로젝트 목록) | 있음 |
| `/projects/:projectId` | 프로젝트 상세 | 있음 |
| `/projects/:projectId/tasks/:taskId` | Task 상세 | 있음 |
| `/trash` | 휴지통 | 있음 |
| 그 외 모든 주소 | 페이지를 찾을 수 없습니다 | 있음 |

- `AppRoutes`(경로 정의만)와 `App`(브라우저 주소와 연결하는 `BrowserRouter` 포함)을 분리해, 테스트에서는 메모리 주소로 경로를 검증.
- 요구사항(requirements-addendum.md)의 "로그인/회원가입을 제외한 모든 페이지에 일관된 내비게이션 바"를 레이아웃 라우트(`AppLayout`)로 구현. 링크는 대시보드, 휴지통.

## 변경 파일
- `frontend/src/App.tsx` (전면 교체)
- `frontend/tests/unit/App.test.tsx`, `frontend/tests/setup.ts` (신규)
- `frontend/vite.config.ts` (Vitest 설정), `frontend/tsconfig.app.json` (`tests` 포함)
- `frontend/package.json` (react-router-dom, Vitest/Testing Library, `test` 스크립트)
- 삭제: `frontend/src/App.css`, `frontend/src/assets/` (Vite 템플릿 데모 파일, 더 이상 참조되지 않음)
- `specs/001-ai-code-learning-platform/tasks.md` (T018 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 템플릿 `App`으로 18개 모두 실패 확인
- GREEN: 구현 후 18개 모두 통과
- REFACTOR: Prettier 정리, ESLint/`tsc` 통과, 빌드 성공 후 재실행하여 18개 통과 유지
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (문장 8/8, 함수 6/6)
- 검증 범위: 7개 경로의 제목, URL 파라미터 표시, 알 수 없는 주소와 `/tasks/7`(프로젝트 없는 Task) 처리, 내비게이션 바 표시/숨김, 링크 주소, 클릭 이동(새로고침 없음), `BrowserRouter`가 실제 URL을 읽는지

## 기술 결정
- 주소 체계는 문서에 명시되지 않아 plan.md의 페이지 목록과 REST 계층 구조(`/projects/:id/tasks/:id`)를 따라 정함. 이후 Task에서 바뀔 수 있음.
- 로그인 보호(`ProtectedRoute`)는 T037에서 추가. 지금은 모든 경로가 공개 상태.
- 자리표시 페이지는 `pages/` 파일을 미리 만들지 않고 `App.tsx` 안의 작은 컴포넌트로 둠. 실제 페이지 Task에서 `element`만 교체하면 되고, 지울 파일이 남지 않음.
- 테스트 도구: Vitest 5 + React Testing Library + jsdom (헌법 지정 스택). `npm test`는 `vitest run`. 테스트 파일도 `tsc` 타입 검사와 ESLint 대상에 포함.
- `react-router-dom` 7 사용 (`react-router`의 재노출 패키지).

## 비고
- `npm audit`에 중간 등급 13건이 표시됨. 모두 ESLint 개발 도구가 쓰는 `minimatch`의 서비스 거부 취약점(개발용 의존성)이 원인이며, 운영 의존성은 `npm audit --omit=dev` 기준 0건. `--force` 수정은 ESLint 체계를 깨뜨릴 수 있어 적용하지 않음. 상위 패키지 업데이트를 지켜볼 것.
- 다음 작업: T019 (TanStack Query 클라이언트), T020 (axios API 클라이언트), T021 (Zustand 인증 스토어), T022 (Tailwind/shadcn).
