# TASK-082. T082 ProjectDetail 의 Task 목록과 생성

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
`ProjectDetail`의 "Task 타임라인" 자리표시자를 실제 Task 목록으로 바꿨습니다. 헤더에 "새 Task" 버튼(`CreateTaskModal` 열기), 로딩("Task를 불러오는 중..."), 오류(`errorMessage` + "다시 시도"), 빈 상태("아직 Task가 없습니다. 첫 Task를 만들어 보세요."), 목록(`ol`, 서버가 준 task_number 오름차순 그대로 `TaskCard`)을 구현했습니다. 카드를 누르면 `/tasks/:taskId`로 이동합니다. 생성이 끝나면 목록이 다시 조회되어 새 Task가 나타납니다.

기존 `project-pages.test.tsx`를 갱신했습니다. 자리표시자 문구("Task 추가 기능은 곧 제공됩니다.") 단언을 빈 상태 문구로 바꿨고, 이제 Task 목록 요청(`GET /projects/p-1/tasks`)이 함께 나가므로 해당 모킹을 추가했으며, "취소해도 다른 요청이 없다" 단언은 프로젝트와 Task 조회 두 개만 있음을 확인하도록 바꿨습니다(의도 유지, 약화/삭제 없음).

## 변경 파일
- `frontend/src/pages/ProjectDetail.tsx` (수정)
- `frontend/tests/unit/task-pages.test.tsx` (생성)
- `frontend/tests/unit/project-pages.test.tsx` (수정: 위 설명)

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- Task 수정/삭제 UI는 범위 밖이라 만들지 않았습니다.

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 프로젝트가 로드된 뒤에야 Task 목록 영역을 보여 주므로 두 단계 로딩이 보일 수 있습니다(요청 자체는 동시에 나갑니다).
