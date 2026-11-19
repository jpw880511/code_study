# TASK-020. axios API 클라이언트 기본 설정

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
서버와 통신하는 "전화기 한 대"를 정해 두는 작업입니다. 모든 화면이 같은 전화기로 서버에 연락하고, 서버가 보낸 오류 답장을 앱이 이해하기 쉬운 한 가지 모양으로 바꿔 줍니다. `frontend/src/services/api-client.ts`에 다음을 구현했습니다.
- `apiClient`(axios 인스턴스): 기본 주소 `http://localhost:8000/api/v1`(환경변수 `VITE_API_BASE_URL`이 있으면 그 값), 쿠키 전송 켬(`withCredentials`, JWT가 HTTP-only 쿠키로 오가므로), 제한 시간 30초, `Accept: application/json`.
- `ApiError`와 `isApiError`: 백엔드 오류 응답(`error`, `message`, `details`, `suggestion`)을 그대로 담은 오류 객체. `status`, `code`, `message`, `details`, `suggestion`을 가짐.
- 응답 인터셉터가 오류를 `ApiError`로 변환
  - 서버가 정해진 형식으로 답함: 서버의 코드와 한국어 메시지를 그대로 사용 (예: 404 `not_found`).
  - 형식이 다름(HTML 오류 페이지, 빈 응답 등): `http_error`와 "요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요."
  - 서버에 연결 불가: `network_error`, 상태 번호 없음.
  - 시간 초과: `timeout`.
  - 요청 취소(TanStack Query의 취소): 변환하지 않고 그대로 통과.
- 개발용 데모 컴포넌트(`QueryDemo`)를 `fetch`에서 이 클라이언트로 옮겨, 실제 브라우저에서 클라이언트를 검증할 수 있게 함.

## 변경 파일
- `frontend/src/services/api-client.ts` (신규)
- `frontend/src/components/dev/QueryDemo.tsx` (`fetch` → `apiClient`)
- `frontend/tests/unit/api-client.test.ts` (신규), `frontend/tests/unit/QueryDemo.test.tsx` (모킹 방식 변경)
- `frontend/package.json` (`axios` 1.21)
- `specs/001-ai-code-learning-platform/tasks.md` (T020 체크)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈 없음으로 실패 확인. 데모 이전도 테스트를 먼저 바꿔 6개 실패 확인
- GREEN: 구현 후 API 클라이언트 24개 테스트가 첫 실행에서 통과, 데모 이전 후 전체 82개 통과
- REFACTOR: Prettier/ESLint/`tsc`/빌드 통과 후 재실행 82개 유지
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 문장 100%, 분기 98.3% (남은 1개는 데모의 선택적 분기)
- 검증 범위: 기본 설정과 환경변수 적용, 요청 본문 JSON 직렬화, 오류 변환(404/409/422/형식 불명 5종/네트워크/시간 초과 2종), 취소 요청 통과, HTTP가 아닌 오류 통과, T019의 재시도 규칙과의 연동(404는 재시도 안 함, 500과 네트워크 오류는 재시도)
- 실제 브라우저(Chrome) 검증: 성공, 404 `not_found`, 409 `conflict`, 그리고 백엔드를 실제로 꺼 둔 상태에서 `network_error` 메시지 확인. 백엔드 로그로 요청 수 확인, 콘솔 오류 없음

## 기술 결정
- 토큰은 쿠키로 전달되므로(research.md) Authorization 헤더를 붙이지 않고 `withCredentials`만 켬. 백엔드 CORS가 이미 특정 출처 + 자격 증명 허용이라 브라우저에서 정상 동작함을 확인.
- `ApiError`가 `status`를 최상위에 가지므로 T019의 `getErrorStatus`/`shouldRetry`를 수정하지 않고 그대로 동작함.
- 취소 요청은 변환하지 않음. 변환하면 TanStack Query가 취소를 오류로 오인할 수 있기 때문.
- 401 처리(로그인 화면으로 이동, 토큰 갱신)와 CSRF 헤더(이중 제출 쿠키)는 인증 Task(T021, T037 등)에서 추가. 지금 넣으면 사용처 없이 추측으로 만들게 됨.
- 오류 본문의 값은 문자열일 때만 신뢰하고 그 외에는 일반 메시지로 대체해, 예상 밖 응답에도 화면이 깨지지 않게 함.

## 비고
- 운영 번들에 데모 코드는 들어가지 않음(검색 확인). 다만 `api-client` 모듈은 인터셉터 등록이라는 부수효과 때문에 아직 사용처가 없어도 번들(axios 약 59KB)에 포함되어 있음. 인증 Task에서 곧 사용되므로 그대로 둠.
- 개발용 데모(`/dev/query-demo`)는 이후 필요 없어지면 컴포넌트와 App.tsx의 경로를 삭제하면 됨.
- 다음 작업: T021 (Zustand 인증 스토어), T022 (Tailwind/shadcn).
