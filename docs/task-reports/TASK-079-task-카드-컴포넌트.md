# TASK-079. T079 TaskCard 컴포넌트 (Task 타임라인 카드)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
`TaskCard`는 `/tasks/:id`로 가는 링크 카드이며 `Task {번호}`, 제목, 설명(있을 때), 감지 언어, 복잡도(초급/중급/고급), 파일 수, 줄 수, 생성일을 보여 줍니다. 업로드가 없으면 "업로드된 코드가 없습니다."를 표시합니다. 기존 `ProjectCard`와 같은 링크+카드 구조를 따랐습니다.

## 변경 파일
- `frontend/src/components/task/TaskCard.tsx` (생성)
- `frontend/src/lib/task-labels.ts`
- `frontend/tests/unit/task-components.test.tsx`

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- 복잡도 라벨과 파일 크기 표기는 TaskDetail/확인 화면과 공유하도록 `task-labels.ts`에 두었습니다.

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 언어는 서버가 준 값(`python` 등)을 그대로 보여 줍니다(한국어 표시 이름 매핑 없음).
