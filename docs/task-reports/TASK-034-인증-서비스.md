# TASK-034. 인증 서비스 (auth-service)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
서버 `/auth` 창구에 대한 전화번호부입니다. `frontend/src/services/auth-service.ts`에 `apiClient` 위의 얇은 함수 5개를 만들었습니다. 스토어는 건드리지 않습니다.
- `register(email, password)` → `POST /auth/register`, `AuthUser` 반환
- `login(email, password)` → `POST /auth/login`, `AuthUser` 반환
- `me()` → `GET /auth/me`, `AuthUser` 반환
- `logout()` → `POST /auth/logout`, 반환값 없음
- `refresh()` → `POST /auth/refresh`, 반환값 없음
오류는 `api-client`가 만든 `ApiError`(status/code/message)가 그대로 전달됩니다.

## 변경 파일
- `frontend/src/services/auth-service.ts` (신규)
- `frontend/src/stores/auth-store.ts` (`AuthUser.skill_level`을 `string | null`로 넓힘)
- `frontend/tests/unit/auth-service.test.ts` (신규, 9개)
- `frontend/tests/helpers/mock-api.ts` (신규, 가짜 axios 어댑터 공통 도구. 이후 테스트들이 공유)

## TDD 결과
- RED: 테스트 먼저 작성 → 모듈 없음으로 실패 확인
- GREEN: 구현 후 9개 통과
- REFACTOR: 별도 정리 없음(함수가 단순). ESLint 규칙(훅 이름 오인)에 맞춰 도우미 이름을 `mockApi`로 변경
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: auth-service 100%
- 검증 범위: 함수별 메서드/URL/본문, 반환값, 오류 4종(409/401 등) 전파

## 기술 결정
- **API 계약에 맞춰 `skill_level`을 `string | null`로 변경.** 새 사용자는 아직 수준이 정해지지 않았기 때문입니다. 기존 스토어 테스트는 영향 없음.
- 백엔드가 아직 없으므로 가짜 어댑터로만 검증. 실제 연동은 수동 테스트(T039~T042)에서 확인 필요.
- tasks.md는 register/login/logout만 언급하지만 계약에 맞춰 `me`, `refresh`도 포함했습니다(T038이 필요).

## 비고
- 토큰은 HttpOnly 쿠키라 이 파일에 토큰 처리 코드가 없습니다.
