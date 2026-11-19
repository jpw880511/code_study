# TASK-054. T054 Dashboard 페이지

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
`pages/Dashboard.tsx`가 "/"의 자리표시자를 대체합니다. h1 "대시보드", "새 프로젝트" 버튼이 있는 헤더, 프로젝트 `ProjectCard`를 담은 반응형 그리드(`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`, `aria-label="프로젝트 목록"`인 목록), 로딩(`role="status"`), 오류(메시지 + "다시 시도"), 빈 상태("아직 프로젝트가 없습니다. 첫 프로젝트를 만들어 보세요." + 자체 "새 프로젝트" 버튼)를 제공합니다.

## 변경 파일
- `frontend/src/pages/Dashboard.tsx` (신규)
- `frontend/tests/unit/project-pages.test.tsx` (신규, Dashboard 부분)

## TDD 결과
- RED: 페이지 모듈 없음으로 import 실패 확인. GREEN: 구현 후 통과. REFACTOR: 없음.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- 작업 개수 같은 아직 없는 데이터는 표시하지 않습니다(계약에 없음).
- 빈 상태에서는 헤더 버튼과 빈 상태 버튼이 둘 다 "새 프로젝트"라서 같은 이름이 2개 존재합니다(요구사항대로).

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
