# TASK-083. T083 TaskDetail 페이지 (문서/연습문제/Q&A 탭 뼈대)와 라우트

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
`/tasks/:taskId` 라우트(보호된 라우트)와 `TaskDetail` 페이지를 추가했습니다. 헤더(`Task {번호}`, 제목 h1, 설명 또는 "설명이 없습니다.", "언어: ...", "복잡도: ..."), 업로드된 파일 목록, 탭 3개(문서/연습문제/Q&A)가 있고 각 탭은 "... 기능은 준비 중입니다." 자리표시자입니다. 로딩 상태, 404/403은 "대시보드로 돌아가기" 링크만(ProjectDetail 방식), 그 밖의 오류는 "다시 시도"를 제공합니다. 위쪽에 `/projects/{project_id}`로 가는 "프로젝트로 돌아가기" 링크가 있습니다.

`App.tsx`에서 기존 자리표시자 라우트 `/projects/:projectId/tasks/:taskId`(TaskPage)를 계약의 `/tasks/:taskId`로 교체했습니다. 따라서 `App.test.tsx`를 갱신했습니다. "두 ID를 보여 주는 자리표시자" 테스트는 `GET /tasks/t-77` 모킹으로 실제 페이지 제목을 확인하도록, "프로젝트 없는 task URL은 404" 테스트는 옛 중첩 URL이 더는 매칭되지 않는 것을 확인하도록 바꿨고, 보호 라우트/내비게이션 목록의 `/projects/p1/tasks/1`은 `/tasks/1`로 바꿨습니다.

## 변경 파일
- `frontend/src/pages/TaskDetail.tsx` (생성)
- `frontend/src/App.tsx` (수정)
- `frontend/tests/unit/task-pages.test.tsx`
- `frontend/tests/unit/App.test.tsx` (수정: 위 설명)

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- 옛 중첩 라우트는 남겨 두지 않았습니다(죽은 라우트 방지, 계약은 `/tasks/:taskId`).
- 탭 내용은 기능이 없는 자리표시자뿐이라 최소 구현입니다.

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 화면에는 Task가 속한 프로젝트 이름이 없습니다(응답에 없음). 되돌아가기는 `project_id`로 링크합니다.
