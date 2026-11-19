# TASK-106. T106 `document-service.ts`와 훅 `useDocument.ts` (문서 가져오기, 상태 폴링)

## 상태
완료 (axios 어댑터 모킹으로 검증, 실제 서버 미연동)

## 날짜
2026-11-18

## 작업 요약
`contracts/phase6-document-generation-api.md` 1, 2, 6번을 그대로 구현했습니다.

- `src/services/document-service.ts`: 타입 `DocumentStatus`, `DocumentStatusInfo`, `TaskDocument`, `DocumentContent`, 챕터별 타입(`Chapter1`~`Chapter7`, `LineExplanation` 등)과 `getDocumentStatus(taskId)`(`GET /tasks/{id}/document/status`), `getDocument(taskId)`(`GET /tasks/{id}/document`). **404 `document_not_found`는 오류가 아니라 `null`**("문서 없음")을 돌려줍니다. `task_not_found`(404), 403, 네트워크 오류 등은 그대로 던집니다.
- `src/hooks/useDocument.ts`:
  - `useDocumentStatus(taskId)`: 상태가 `pending`/`in_progress`일 때만 **2초마다** 폴링하고, `completed`/`failed`/문서 없음(null)이면 멈춥니다. 컴포넌트가 사라지면 TanStack Query가 폴링을 멈춥니다. `staleTime: 0`.
  - `useTaskDocument(taskId, enabled)`: 완료됐을 때만 문서를 한 번 가져옵니다(`staleTime: Infinity`).
  - `useTaskCode(taskId, enabled)`: 기존 `getTaskCode`(`GET /tasks/{id}/code`)를 씁니다.
  - 쿼리 키: `['tasks', id, 'document', 'status']`, `['tasks', id, 'document']`, `['tasks', id, 'code']`(기존 `['tasks', id]`와 같은 접두사).

## 변경 파일
- `frontend/src/services/document-service.ts` (생성)
- `frontend/src/hooks/useDocument.ts` (생성)
- `frontend/tests/unit/document-service.test.ts` (생성, 5개)
- `frontend/tests/unit/useDocument.test.tsx` (생성, 10개)
- `frontend/tests/helpers/document-fixtures.ts` (생성: 상태/문서/코드 테스트 데이터)

## TDD 결과
- 훅: 모듈 없음으로 RED 확인 후 구현했습니다. 서비스는 테스트와 구현을 연달아 작성했고 별도 RED 실행은 하지 않았습니다(솔직히 기록).
- GREEN: 서비스 5개(상태 반환, `document_not_found` -> null, 다른 오류는 유지, 문서 반환 및 null/403), 훅 10개(가짜 타이머: pending/in_progress는 2초(1.9초에는 아직 아님)마다 폴링, completed/failed는 폴링 없음, 완료로 바뀌면 중단, 언마운트하면 중단, 문서 없음이면 폴링 없음, 문서는 활성화 전에는 요청 없고 활성화 후 1회, 코드는 비활성 동안 요청 없음).
- 전체 506개 통과.

## 기술 결정
- `document_not_found`를 서비스에서 `null`로 바꿨습니다. 호출하는 쪽에서 오류 처리와 "문서 없음" 처리를 섞지 않게 하기 위해서입니다.
- 재시도: 앱 기본 설정(4xx는 재시도 없음, 5xx/네트워크는 2회)을 그대로 씁니다.

## 비고
- 폴링 도중 요청이 실패해도(일시적 5xx) 마지막으로 받은 상태가 있으면 폴링은 계속됩니다.
- 상태가 `completed`인데 `GET /document`의 `content`가 null이거나 문서가 404면 뷰어가 오류 문구를 보여 줍니다(계약상 일어나지 않아야 하는 경우).
