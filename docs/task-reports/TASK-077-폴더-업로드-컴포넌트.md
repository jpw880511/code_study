# TASK-077. T077 FolderUpload 컴포넌트 (webkitdirectory, 폴더 구조 보존)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
`webkitdirectory` 입력으로 폴더를 고르는 `FolderUpload`를 만들었습니다("폴더 선택" 라벨). 각 파일의 `webkitRelativePath`를 상대 경로로 보존하고(없으면 파일 이름), 전송 전에 `.git`, `node_modules`, `__pycache__` 디렉터리 안의 파일과 `.DS_Store`를 걸러서 "일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__ (제외된 파일 N개)" 안내를 `role="status"`로 보여 줍니다. 경로는 React가 텍스트로 렌더링하며 `dangerouslySetInnerHTML`은 쓰지 않았습니다. 새 폴더를 고르면 이전 선택을 대체합니다.

## 변경 파일
- `frontend/src/components/upload/FolderUpload.tsx` (생성)
- `frontend/src/lib/upload-validation.ts` (`toFolderEntries`, `splitExcluded`)
- `frontend/tests/unit/upload-components.test.tsx`

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- React 타입에 `webkitdirectory`가 없어 `{...{ webkitdirectory: '' }}` 스프레드로 전달했습니다.
- 제외 판정은 계약대로 "디렉터리 이름"이 일치하거나 파일 이름이 `.DS_Store`일 때입니다(이름이 `node_modules`인 일반 파일은 제외하지 않음).

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 폴더가 매우 커도(수천 개) 브라우저는 모든 항목을 한 번에 읽습니다. 제외된 경로는 개수만 보여 주고 목록은 보여 주지 않습니다.
