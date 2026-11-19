# TASK-051. T051 ProjectCard 컴포넌트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
프로젝트 목록에 쓰이는 카드입니다. `frontend/src/components/project/ProjectCard.tsx`는 shadcn `Card`로 제목, 설명(최대 3줄로 잘림, `null`이면 요소 자체를 그리지 않음), "마지막 활동: <날짜>"를 보여 주고, 카드 전체가 `/projects/:id`로 가는 링크입니다. 링크의 접근 가능한 이름은 제목을 포함합니다. 날짜는 `lib/format-date.ts`(`Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' })`)로 "2026년 11월 3일" 형태로 표시합니다.

## 변경 파일
- `frontend/src/components/project/ProjectCard.tsx` (신규)
- `frontend/src/lib/format-date.ts` (신규)
- `frontend/tests/unit/project-components.test.tsx` (신규, ProjectCard 4개 케이스)
- `frontend/tests/unit/format-date.test.ts` (신규, 3개)
- `frontend/tests/helpers/project-fixtures.ts` (신규, `makeProject`)

## TDD 결과
- RED: 테스트 먼저 작성 → `ProjectCard`/`format-date` 모듈이 없어 import 실패 확인. GREEN: 구현 후 통과. REFACTOR: 날짜 포맷을 별도 모듈로 분리해 상세 페이지와 공유.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- **날짜는 `dateStyle: 'long'`**, 시간대는 브라우저 로컬. 테스트는 정오(UTC) 시각을 써서 어느 시간대에서도 같은 날짜가 나오게 했습니다.
- **시간대 표시가 없는 문자열은 UTC로 해석**합니다. 서버가 naive datetime을 "Z" 없이 보낼 가능성에 대한 방어입니다(계약은 UTC ISO 문자열).
- 카드 전체를 `<a>`로 감싸고 그 안에 `Card`를 둠(중첩 링크/버튼 없음).

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
