# TASK-052. T052 CreateProjectModal 컴포넌트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
새 프로젝트 생성 대화상자입니다. `CreateProjectModal.tsx`는 shadcn `Dialog`(`open`/`onOpenChange`로 제어)와 공용 폼 `ProjectForm.tsx`로 구성됩니다. 제목(필수, 트림 후 1~255자)과 설명(선택, 최대 2000자, "N자 남음" 힌트)을 받고, 클라이언트 검증(`lib/project-validation.ts`)은 빠른 피드백용이며 최종 판단은 서버입니다. 서버 오류(`ApiError.message`)는 `role="alert"`에 표시, 제출 중에는 버튼 비활성화("만드는 중...") 및 중복 제출 차단(`useFormSubmission` 재사용), 취소/Escape는 제출하지 않고 닫기만 합니다. 대화상자 내용은 닫히면 언마운트되므로 다시 열면 폼이 초기화됩니다. 값은 트림되어 전송되고 빈 설명은 필드 자체를 생략합니다.

## 변경 파일
- `frontend/src/components/project/CreateProjectModal.tsx` (신규)
- `frontend/src/components/project/ProjectForm.tsx` (신규, 생성/수정 공용 폼)
- `frontend/src/lib/project-validation.ts` (신규)
- `frontend/tests/unit/project-components.test.tsx` (CreateProjectModal 12개 케이스)
- `frontend/tests/unit/project-validation.test.ts` (신규)

## TDD 결과
- RED: 모듈 없음으로 import 실패 확인. GREEN: 구현 후 통과. REFACTOR: 폼 본문을 `ProjectForm`으로 분리(수정 대화상자와 공유), 오류 문구 헬퍼 `lib/error-message.ts` 분리.
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%에 가까움 (전체 99.7%, 분기 98.7%)

## 기술 결정
- **폼 로직은 `ProjectForm`에 한 번만 구현**하고 생성/수정이 공유합니다(T055의 수정 기능).
- 폼 상태 초기화는 별도 코드 없이 Radix `DialogContent` 언마운트에 의존합니다(테스트로 검증).
- 필드 오류에는 `role="alert"`를 쓰지 않고 서버 오류 한 곳으로 한정(TASK-032와 동일 결정).

## 비고
- 백엔드 엔드포인트는 병렬로 개발 중이어서 모킹된 axios 어댑터로만 검증했습니다.
- 인증 정보는 Zustand 스토어와 HttpOnly 쿠키에만 있으며 localStorage/sessionStorage는 사용하지 않습니다.
