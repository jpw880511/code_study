# TASK-053. T053 프로젝트 서비스와 TanStack Query 훅

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`services/project-service.ts`에 `Project`/입력 타입과 `listProjects`, `createProject`, `getProject`, `updateProject`, `deleteProject`를 `apiClient` 위에 얇게 구현했습니다(스토어/React 접근 없음). `hooks/useProjects.ts`에는 `useProjects`(키 `['projects']`), `useProject(id)`(키 `['projects', id]`), `useCreateProject`, `useUpdateProject(id)`, `useDeleteProject`가 있습니다. 생성/수정/삭제 성공 시 목록을 무효화하고(수정은 상세도), 삭제는 상세 캐시를 제거합니다. 낙관적 업데이트는 사용하지 않았습니다.

## 변경 파일
- `frontend/src/services/project-service.ts` (신규)
- `frontend/src/hooks/useProjects.ts` (신규)
- `frontend/src/lib/error-message.ts` (신규)
- `frontend/tests/unit/project-service.test.ts` (신규, 8개)
- `frontend/tests/unit/useProjects.test.tsx` (신규, 6개)

## TDD 결과
- RED: 모듈 없음으로 import 실패 확인. GREEN: 구현 후 통과. REFACTOR: 없음(처음부터 얇은 구조).
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- **`onSuccess`에서 `invalidateQueries`의 Promise를 반환**하여 mutation이 목록 재조회까지 기다립니다. 모달이 닫히는 시점에 새 목록이 이미 화면에 있습니다.
- 무효화는 `exact: true`로 목록 키만 대상으로 해, 다른 프로젝트의 상세 캐시를 불필요하게 다시 받지 않습니다.
- 수정 입력은 전달한 키만 전송합니다(부분 수정). 명시적 `null` 설명은 설명 삭제를 뜻합니다.

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
