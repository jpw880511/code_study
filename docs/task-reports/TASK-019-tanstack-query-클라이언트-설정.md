# TASK-019. TanStack Query 클라이언트 설정

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
서버에서 받아 온 데이터를 "잠깐 보관해 두는 메모장"의 사용 규칙을 정한 작업입니다. 같은 데이터를 화면마다 서버에 다시 묻지 않고, 실패했을 때 몇 번 더 시도할지를 한곳에서 정합니다. `frontend/src/lib/queryClient.ts`에 다음을 구현했습니다.
- `queryClient`: 앱 전체가 함께 쓰는 하나의 클라이언트.
- `createQueryClient()`: 테스트마다 새 클라이언트를 만들기 위한 생성 함수.
- 기본 규칙
  - 받은 데이터는 1분 동안 "신선"하다고 보고 같은 요청을 서버에 다시 보내지 않음(research.md의 stale-while-revalidate 캐싱).
  - 브라우저 창에 다시 포커스가 와도 자동으로 다시 불러오지 않음.
  - 조회 실패 시 400번대 오류(로그인 필요, 없음, 충돌, 검증 실패, 요청 과다 등)는 다시 시도해도 결과가 같으므로 재시도하지 않고, 네트워크 오류와 500번대는 최대 2번 재시도(총 3번 호출). 재시도 간격은 1초, 2초, 4초로 늘리고 최대 10초.
  - 생성/수정/삭제(mutation)는 재시도하지 않음(중복 생성을 막기 위해).
- `getErrorStatus`, `shouldRetry`: 오류에서 HTTP 상태 번호를 읽는 함수와 재시도 판단 함수(axios 오류 `error.response.status`와 단순 `status` 모두 지원).
- `main.tsx`: 앱 전체를 `QueryClientProvider`로 감싸 모든 화면에서 같은 클라이언트를 쓰도록 연결.

## 변경 파일
- `frontend/src/lib/queryClient.ts` (신규)
- `frontend/src/main.tsx` (Provider 연결)
- `frontend/tests/unit/queryClient.test.ts`, `frontend/tests/unit/main.test.tsx` (신규)
- `frontend/package.json` (`@tanstack/react-query` 5.105)
- `specs/001-ai-code-learning-platform/tasks.md` (T019 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈 없음으로 실패 확인. Provider 연결 테스트도 먼저 작성해 "No QueryClient set" 오류로 실패 확인
- GREEN: 구현 후 전체 47개 통과 (T018의 18개 포함)
- REFACTOR: Prettier 정리 후 ESLint, `tsc`, Vite 빌드 통과, 재실행 47개 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100% (문장 24/24, 분기 13/13, 함수 10/10)
- 검증 범위: 상태 번호 추출, 재시도 판단(4xx/5xx/네트워크), 기본값, 지수 백오프와 상한, 실제 `fetchQuery` 동작(404는 1번 호출, 500 후 성공은 2번, 계속 실패하면 3번 호출, 변경 요청은 1번, 신선한 캐시는 재호출 안 함), 실제 `main.tsx`를 불러와 앱 내부에서 같은 클라이언트가 제공되는지

## 기술 결정
- 재시도 횟수 2회와 신선 시간 60초는 일반적인 시작값으로 정했고, 실제 사용 중 조정 가능. 값은 파일 상단 상수로 분리.
- 429(요청 과다)도 재시도하지 않음. 곧바로 다시 보내면 제한이 더 길어지고, 서버가 알려 주는 대기 시간을 화면에서 안내하는 편이 낫기 때문.
- 개발 도구(devtools) 패키지는 아직 필요하지 않아 설치하지 않음.
- 오류 상태 추출을 별도 함수로 둔 이유: T020에서 만들 axios 클라이언트의 오류 모양에 의존하지 않고 먼저 구현·테스트할 수 있게 하기 위해.

## 비고
- 다음 작업: T020 (axios API 클라이언트), T021 (Zustand 인증 스토어), T022 (Tailwind/shadcn).
