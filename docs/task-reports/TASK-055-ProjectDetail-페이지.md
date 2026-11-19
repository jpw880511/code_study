# TASK-055. T055 ProjectDetail 페이지 (수정/삭제 포함)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`pages/ProjectDetail.tsx`가 `/projects/:projectId`의 자리표시자를 대체합니다. h1은 프로젝트 제목이며 설명(없으면 흐린 "설명이 없습니다."), 생성일/마지막 활동, 대시보드로 돌아가는 링크, "Task 타임라인" 섹션(자리표시 문구 "아직 Task가 없습니다. Task 추가 기능은 곧 제공됩니다.")을 보여 줍니다. 로딩은 `role="status"`, 오류는 `role="alert"`: 404/403은 서버 메시지 + 대시보드 링크(재시도 없음), 그 밖의 오류는 메시지 + "다시 시도".

**tasks.md의 빈틈 보완(요청에 따른 추가):** 이후 수동 테스트 T059(제목 수정 후 유지 확인), T060(삭제 후 소프트 삭제 확인)에 필요한 UI가 tasks.md에 없어, 이 페이지에 "수정"과 "삭제"를 추가했습니다. "수정"은 `EditProjectModal`(공용 `ProjectForm`, 제목/설명, 성공 시 페이지와 대시보드 목록이 갱신됨, 설명을 비우면 `null`로 전송), "삭제"는 `DeleteProjectDialog`(확인 문구 "이 프로젝트를 삭제할까요? 프로젝트와 안의 모든 Task가 휴지통으로 이동하며 30일 동안 복구할 수 있습니다.", 취소/삭제, 성공 시 "/"로 이동, 실패 시 alert)입니다.

## 변경 파일
- `frontend/src/pages/ProjectDetail.tsx` (신규)
- `frontend/src/components/project/EditProjectModal.tsx` (신규, 빈틈 보완)
- `frontend/src/components/project/DeleteProjectDialog.tsx` (신규, 빈틈 보완)
- `frontend/src/App.tsx` (자리표시자 `ProjectPage` 제거, 실제 페이지 연결 - T056 보고서 참고)
- `frontend/tests/unit/project-pages.test.tsx` (ProjectDetail 부분)

## TDD 결과
- RED: 페이지 모듈 없음으로 import 실패 확인. GREEN: 구현 후 통과. REFACTOR: 확인 대화상자 닫힘 처리를 단순화(불필요한 분기 제거).
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- 삭제 성공 시 상세 캐시를 먼저 제거한 뒤 이동하므로 삭제된 프로젝트를 다시 조회(404)하지 않습니다(테스트로 검증).
- 삭제 확인에는 요청대로 `AlertDialog` 대신 `Dialog`를 사용했습니다.
- 휴지통 화면은 아직 없으므로 "복구" 동선은 문구로만 안내됩니다.

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
