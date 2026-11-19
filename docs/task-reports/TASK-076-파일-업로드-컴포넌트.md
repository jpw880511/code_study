# TASK-076. T076 FileUpload 컴포넌트 (드래그앤드롭 + 파일 선택기)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
여러 파일을 끌어다 놓거나 선택할 수 있는 `FileUpload`를 만들었습니다. 드롭 영역은 숨겨진 파일 입력을 감싼 `label`이라 키보드로 입력에 포커스해 선택기를 열 수 있습니다("파일 선택" 라벨). 선택한 파일은 목록(이름, 크기)으로 보이고, 이미 고른 파일(이름+크기+수정시각이 같음)은 무시하며, 파일마다 "제거" 버튼이 있습니다. 검증 오류는 `role="alert"`로 표시합니다. 검증 상수와 규칙은 `src/lib/upload-validation.ts` 한 곳에 두었습니다(확장자 12개, 10MB, 1~20개, 제목/설명 길이, 붙여넣기 언어 목록, 제외 폴더/파일).

## 변경 파일
- `frontend/src/components/upload/FileUpload.tsx` (생성)
- `frontend/src/lib/upload-validation.ts` (생성)
- `frontend/src/lib/task-labels.ts` (생성: 파일 크기 표기, 복잡도 라벨)
- `frontend/tests/unit/upload-components.test.tsx` (생성)
- `frontend/tests/unit/upload-validation.test.ts` (생성)
- `frontend/tests/unit/task-labels.test.ts` (생성)
- `frontend/tests/helpers/task-fixtures.ts` (생성)

## TDD 결과
- RED: 구현 전에 테스트를 먼저 작성하고 `npx vitest run`으로 모듈 없음/라우팅 부재로 실패하는 것을 확인했습니다. GREEN: 구현 후 전체 통과. 전체 결과: 399개 통과(작업 전 314개), `npx eslint .` 오류 없음, `npm run build`(tsc 포함) 성공.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일은 문장 100%에 가깝고, 전체는 문장 99.82%, 분기 97.6%

## 기술 결정
- 브라우저 `accept` 속성은 쓰지 않고 확장자 검사를 직접 합니다(오류 문구에 지원 형식을 보여 주기 위해).
- 폴더를 끌어다 놓는 경우는 처리하지 않습니다(폴더는 "폴더 업로드" 탭 사용).

## 비고
- 백엔드(T067~T075)는 병렬로 개발 중이어서 실제 서버 없이 `specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md`만 보고 axios 어댑터 모킹으로 검증했습니다. 실제 연동은 후속 브라우저 테스트에서 확인해야 합니다.
- 바이너리 파일 판별은 브라우저에서 하지 않고 서버(`binary_file_rejected`)에 맡깁니다.
- 드래그 시각 효과는 jsdom 단위 테스트로만 확인했고 실제 브라우저 확인은 하지 않았습니다.
