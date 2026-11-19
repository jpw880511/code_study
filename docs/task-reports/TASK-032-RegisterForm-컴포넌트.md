# TASK-032. RegisterForm 컴포넌트

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
회원가입 신청서 양식입니다. 이메일, 비밀번호, 비밀번호 확인을 받고, 서버에 보내기 전에 눈에 띄는 실수를 바로 알려 줍니다. `frontend/src/components/auth/RegisterForm.tsx`는 화면만 담당합니다. 실제 가입 요청은 부모가 넘겨 주는 `onSubmit`이 하고, 폼은 "처리 중"과 "서버 오류" 표시만 스스로 관리합니다. 이동(navigate)이나 스토어 접근은 하지 않습니다.
- 필드: 이메일(`autocomplete="email"`), 비밀번호와 비밀번호 확인(`type="password"`, `autocomplete="new-password"`). 모든 입력에 `<label>` 연결.
- 클라이언트 검증(빠른 피드백용, 최종 판단은 서버): 필수 입력, 이메일 형태, 비밀번호 8자 이상/영문자 포함/숫자 포함/UTF-8 72바이트 이하, 확인 일치. 필드별 메시지는 입력칸 옆에 표시되고 `aria-describedby`로 연결됨.
- 서버 오류(`ApiError.message`)는 `role="alert"` 요소에 표시. `ApiError`가 아닌 예외는 일반 문구 표시.
- 제출 중에는 버튼이 비활성화되고 "가입 중..."으로 바뀜. ref 잠금으로 빠른 연타/Enter 중복 제출도 차단.

## 변경 파일
- `frontend/src/components/auth/RegisterForm.tsx` (신규)
- `frontend/src/components/auth/FormField.tsx` (신규, 라벨+입력+오류 문구 묶음. LoginForm과 공유)
- `frontend/src/components/auth/useFormSubmission.ts` (신규, 처리 중/서버 오류/중복 제출 방지. LoginForm과 공유)
- `frontend/src/lib/auth-validation.ts` (신규, 검증 규칙)
- `frontend/tests/unit/auth-forms.test.tsx` (신규, LoginForm 테스트와 함께 22개)

## TDD 결과
- RED: 테스트 먼저 작성 → `LoginForm`/`RegisterForm` 모듈이 없어 import 실패 확인
- GREEN: 구현 후 22개 모두 통과 (이 중 RegisterForm 12개 케이스)
- REFACTOR: 두 폼의 공통 부분을 `FormField`, `useFormSubmission`, `auth-validation`으로 분리. 이후 중복 제출 방어 분기를 `fireEvent.submit`으로 직접 검증하도록 테스트 보강. 전체 재실행 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 이 Task의 파일 전체 문장 100%, 분기 100%
- 검증 범위: 라벨/속성(autocomplete, type), 제출 값(이메일 앞뒤 공백 제거, 확인 값은 전달 안 함), 필수/형식/비밀번호 규칙 4종/72바이트 경계(정확히 72바이트 허용)/불일치 메시지, 서버 오류 alert, 일반 오류 문구, 제출 중 비활성화와 중복 제출 차단

## 기술 결정
- **검증은 서버 규칙의 거울일 뿐.** 서버가 최종 권한이므로 클라이언트는 같은 규칙으로 즉시 알려 주기만 합니다. 바이트 수는 `TextEncoder`로 계산하여 한글 3바이트 규칙을 맞췄습니다. 영문자 판정은 `\p{L}`(한글 포함)로, 서버가 영문 외 글자를 허용할 경우와 어긋나지 않도록 느슨하게 잡았습니다. 어긋나면 서버 오류 alert가 보완합니다.
- **`noValidate` + 직접 검증.** 브라우저 기본 말풍선 대신 한국어 메시지와 접근성 연결을 일관되게 제공하기 위함입니다.
- 필드 오류는 `role="alert"`를 쓰지 않음. alert는 서버 오류 하나로 한정해 스크린리더 안내가 겹치지 않게 했습니다.
- 서버의 `validation_error` details를 필드에 매핑하는 기능은 넣지 않았습니다(요구되지 않음). 서버 메시지는 상단 alert에 그대로 표시됩니다.

## 비고
- 이메일은 보내기 전에 앞뒤 공백만 제거합니다. 소문자화는 서버가 합니다.
- 다음 작업: T033 LoginForm (같은 파일에서 함께 구현됨), T035 Register 페이지.
