# TASK-085: 브라우저 테스트 — 폴더 업로드와 폴더 구조 보존

## 상태
완료

## 날짜
2026-11-17

## 작업 요약
폴더를 올리면 폴더 구조가 그대로 보존되고, `.git`, `node_modules` 같은 제외 대상이 걸러지며 안내가 나오는지 확인했다.

## 변경 파일
- `frontend/e2e/tasks.spec.ts` (T085 시나리오)

## TDD 결과
- 검증 항목: 임시 폴더 `my app/`(공백 포함)에 `src/App.jsx`, `src/한글 파일.js`, `public/index.html`과 제외 대상(`node_modules/lib/index.js`, `.git/config`)을 만들어 `webkitdirectory` 입력에 지정 → "일반적인 빌드/시스템 폴더를 제외했습니다" 안내 → 업로드 확인에 세 파일의 전체 경로가 보이고 `node_modules`는 없음 → Task 상세 페이지에서 새로고침한 뒤에도 같은 경로 표시 → DB `code_files.file_path`가 `my app/public/index.html|my app/src/App.jsx|my app/src/한글 파일.js`.
- 결과: 통과.

## 기술 결정
- 구조가 "화면에만" 있는지 "저장까지" 되었는지 구분하려고 새로고침 후 상세 페이지와 DB를 모두 확인한다.
- 경로에 공백과 한글을 넣어 multipart의 `paths` 필드가 인코딩 때문에 깨지지 않는지 함께 확인했다.
- 실제 브라우저에서만 확인할 수 있는 것(`webkitRelativePath` 설정, `files`와 `paths`의 순서 짝짓기)이 이 테스트로 처음 검증되었다. 단위 테스트는 모킹이라 이를 보장하지 못했다.

## 비고
- 임시 폴더는 OS 임시 디렉터리에 만들고 테스트 후 따로 지우지 않는다(OS가 정리).
- 제외 규칙은 브라우저가 먼저 적용하고 서버도 방어적으로 한 번 더 적용한다. 서버 쪽 제외는 이 테스트가 아니라 백엔드 통합 테스트와 실제 HTTP 검증에서 확인했다.
