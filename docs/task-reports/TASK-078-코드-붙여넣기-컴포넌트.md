# TASK-078. T078 PasteCode 컴포넌트 (텍스트 영역 + 언어 드롭다운)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
"프로그래밍 언어" 드롭다운(기본 "언어를 선택하세요", 값은 `python`~`text`, 표시 이름은 Python/C++/텍스트 등으로 분리)과 "코드" 텍스트 영역을 가진 `PasteCode`를 만들었습니다. 오류는 `role="alert"`로 표시합니다. 규칙은 `validatePaste`(언어 필수, 빈 코드, 10MB 순서)에 있고 문구는 계약/명세와 같습니다("업로드하기 전에 프로그래밍 언어를 선택하세요.").

## 변경 파일
- `frontend/src/components/upload/PasteCode.tsx` (생성)
- `frontend/src/lib/upload-validation.ts` (`validatePaste`)
- `frontend/tests/unit/upload-components.test.tsx`

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- 별도 select 컴포넌트가 없어 네이티브 `<select>`를 Tailwind로 꾸몄습니다(접근성과 테스트 용이).

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 붙여넣기 오류는 입력 중에는 보이지 않고 "Task 만들기"를 누른 뒤 표시됩니다(빈 폼을 계속 경고하지 않기 위해).
