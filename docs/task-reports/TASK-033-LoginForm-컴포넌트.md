# TASK-033. LoginForm 컴포넌트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
출입문 인터폰과 같은 로그인 양식입니다. `frontend/src/components/auth/LoginForm.tsx`는 이메일과 비밀번호를 받아 부모가 넘긴 `onSubmit`으로 전달합니다. RegisterForm(TASK-032)과 같은 구조입니다.
- 필드: 이메일(`autocomplete="email"`), 비밀번호(`type="password"`, `autocomplete="current-password"`), 모두 `<label>` 연결.
- 클라이언트 검증: 이메일 필수/형태, 비밀번호 필수. 로그인에는 비밀번호 강도 규칙을 적용하지 않음(옛 규칙으로 만든 계정도 로그인할 수 있어야 하므로).
- 서버 오류(예: 401 `invalid_credentials`의 "이메일 또는 비밀번호가 올바르지 않습니다.")는 `role="alert"`에 표시. 다음 제출 시 이전 오류를 지움.
- 제출 중 버튼 비활성화 + "로그인 중...", 중복 제출 차단.

## 변경 파일
- `frontend/src/components/auth/LoginForm.tsx` (신규)
- 공유 모듈과 테스트는 TASK-032 참조 (`FormField`, `useFormSubmission`, `auth-validation`, `auth-forms.test.tsx`)

## TDD 결과
- RED: TASK-032와 같은 테스트 파일에서 모듈 부재로 실패 확인
- GREEN: LoginForm 케이스 10개 통과
- REFACTOR: 공유 모듈 분리 후 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: LoginForm 문장/분기 100%
- 검증 범위: 라벨/속성, 제출 값과 이메일 공백 제거, 필수/형식 오류, 서버 오류 alert, 일반 오류 문구, 이전 오류 해제, 제출 중 비활성화/중복 제출 차단

## 기술 결정
- 로그인 비밀번호는 "비어 있지 않음"만 검사. 규칙 검사는 가입 때만 하고 인증 판단은 서버에 맡깁니다.
- `Credentials` 타입을 LoginForm에서 내보내 RegisterForm이 재사용합니다.
- 폼은 스토어/라우터를 모릅니다. 로그인 성공 후 처리는 Login 페이지(T036) 책임.

## 비고
- 다음 작업: T036 Login 페이지.
