# TASK-056. T056 프로젝트 생성 흐름과 라우팅 연결

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
Dashboard의 "새 프로젝트" 버튼(헤더, 빈 상태)이 `CreateProjectModal`을 엽니다. 성공하면 모달이 닫히고 목록이 무효화되어 새 프로젝트가 자동으로 나타나며 사용자는 대시보드에 머뭅니다. `App.tsx`에서 "/"와 `/projects/:projectId`의 자리표시자를 실제 `Dashboard`/`ProjectDetail`로 교체했습니다(ProtectedRoute, 레이아웃, 공개 라우트, dev 라우트, Task 자리표시자는 유지).

기존 `App.test.tsx`는 같은 의도를 유지한 채 모킹된 API를 쓰도록 갱신했습니다: 페이지를 `QueryClientProvider`로 감싸고, 프로젝트 페이지 테스트는 `GET /projects/abc-123`을 모킹해 제목을 기대하며, 로그아웃 테스트는 요청 목록에 `POST /auth/logout`이 포함되는지 확인합니다(이제 "/"가 목록도 먼저 조회하므로). 단언을 삭제하거나 약화하지 않았고, 404 표시와 대시보드 목록 라우팅 테스트를 추가했습니다.

## 변경 파일
- `frontend/src/App.tsx` (수정)
- `frontend/tests/unit/App.test.tsx` (수정)
- `frontend/tests/unit/project-pages.test.tsx` (생성 흐름 3개 케이스: 헤더 버튼으로 생성 후 목록 갱신, 빈 상태 버튼, 취소)

## TDD 결과
- RED: App 테스트를 먼저 수정/추가하고 Dashboard 흐름 테스트를 작성 → 모듈/라우팅 부재로 실패 확인. GREEN: 연결 후 전체 통과. 전체 결과: 314개 통과(작업 전 251개), 신규 코드 커버리지 거의 100%(전체 문장 99.7%, 분기 98.7%).
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- 목록 갱신은 서버 응답을 다시 받아서 하므로(낙관적 업데이트 없음) 요청 순서가 `GET /projects` → `POST /projects` → `GET /projects`입니다.
- 백엔드와의 실제 연동 확인은 수동 브라우저 테스트(T057-T060)에서 합니다.

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
