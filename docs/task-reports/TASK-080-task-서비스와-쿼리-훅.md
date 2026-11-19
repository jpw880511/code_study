# TASK-080. T080 task-service 와 useTasks 훅

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
`task-service.ts`에 계약의 타입(`Task`, `TaskUpload`, `CodeFileSummary`, `TaskDetail`, `CreateTaskResult`, `TaskCode`)과 함수(`listTasks`, `createTask`, `getTask`, `updateTask`, `deleteTask`, `getTaskCode`)를 선언했습니다. `createTask`는 `FormData`(`title`, 비어 있지 않을 때만 `description`, `upload_method`, `files` 반복, 폴더면 같은 순서로 `paths` 반복, 붙여넣기면 `code`/`language`)를 만들며 `Content-Type`을 직접 지정하지 않습니다. `useTasks.ts`에는 `useTasks(projectId)`(키 `["projects", id, "tasks"]`), `useTask(id)`(키 `["tasks", id]`), `useCreateTask(projectId)`가 있고, 생성 성공 시 Task 목록, 프로젝트 상세, 프로젝트 목록 캐시를 무효화합니다(프로젝트의 마지막 활동이 갱신되므로).

## 변경 파일
- `frontend/src/services/task-service.ts` (생성)
- `frontend/src/hooks/useTasks.ts` (생성)
- `frontend/tests/unit/task-service.test.ts` (생성)
- `frontend/tests/unit/useTasks.test.tsx` (생성)

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- 입력 형태는 `upload: {method: 'file' | 'folder' | 'paste', ...}` 구분 유니온으로 두어 잘못된 조합(예: 붙여넣기에 files)을 타입으로 막았습니다.
- 목록 무효화는 "확인" 클릭 시점이 아니라 생성 성공 즉시 합니다(확인을 건너뛰고 닫아도 목록이 최신이 되도록). 사용자에게 보이는 결과는 같습니다.

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- `updateTask`/`deleteTask`/`getTaskCode`는 서비스 함수만 있고 훅과 화면은 이번 범위가 아닙니다.
