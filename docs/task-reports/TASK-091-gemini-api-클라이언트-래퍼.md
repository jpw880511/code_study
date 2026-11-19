# TASK-091: Gemini API 클라이언트 래퍼

## 상태
완료

## 날짜
2026-11-17

## 작업 요약
Google Gemini를 부르는 얇은 클라이언트를 만들었다. 프롬프트 하나를 보내 텍스트 하나를 받고, 실패는 "다시 시도하면 될 수 있는 것"과 "아닌 것"으로 나눠서 알려 준다. 재시도 자체(최대 3회, 지수 백오프, FR-090)는 문서 생성과 Q&A가 각자 대기 가능 시간이 달라서 T093 이후의 호출 쪽 몫으로 남기고, 이 클라이언트는 그 판단에 쓸 `retryable` 표시를 제공한다.

## 변경 파일
- `backend/src/services/ai/gemini_client.py` (신규): `GeminiClient.generate()`, `GeminiResponse`
- `backend/src/services/ai/config.py` (신규): `GeminiSettings` (키, 모델, 제한 시간)
- `backend/src/services/ai/errors.py` (신규): AI 오류 4종
- `backend/src/services/ai/__init__.py` (신규, 빈 파일)
- `backend/tests/unit/test_gemini_client.py`, `backend/tests/unit/test_gemini_config.py` (신규, 53개)
- `backend/tests/conftest.py` (AI 설정이 테스트로 새지 않게 하는 공통 장치 추가)
- `.env.example` (선택 설정 `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS` 주석 추가)
- `backend/tests/unit/test_token_service.py` (**내용 변경 없음, 포맷만 정리**. `ruff format tests/unit`를 돌릴 때 함께 정리되어 기존의 유일한 포맷 지적이 사라졌다)

## TDD 결과
- RED: 모듈이 없어 수집 단계에서 실패. 이후 `thinking_tokens` 필드도 같은 방식으로 먼저 RED를 확인한 뒤 추가했다.
- GREEN: 신규 53개 통과. 전체 1297개 통과(건너뜀 0), 커버리지 100%(1654문장, 미커버 0). `ruff check`, `ruff format --check`, `mypy src` 모두 통과.
- 실제 Gemini 호출 확인(임시 스크립트, 스위트에는 넣지 않음; 작은 호출 약 12회): `.env`의 키로 정상 호출 성공, JSON 모드(`{"answer": 2, "language": "ko"}`), 시스템 지시문 적용, 실제 404(없는 모델) → `AIRequestRejectedError`(재시도 불가), 실제 400(잘못된 키) → `AIRequestRejectedError`, 제한 시간 초과 → `AIServiceUnavailableError`(재시도 가능).

## 제공하는 것
| 이름 | 역할 |
|---|---|
| `GeminiClient(settings=None, sdk_client=None).generate(prompt, *, system_instruction, temperature, max_output_tokens, json_output, timeout)` | 모델을 한 번 호출해 `GeminiResponse(text, model, prompt_tokens, completion_tokens, thinking_tokens, finish_reason)` 반환 |
| `GeminiSettings` | `GOOGLE_API_KEY`(`SecretStr`), `GEMINI_MODEL`(기본 `gemini-3-flash-preview`), `GEMINI_TIMEOUT_SECONDS`(기본 120) |
| `AINotConfiguredError` (`ai_not_configured`, 재시도 불가) | 키 없음 |
| `AIServiceUnavailableError` (`ai_unavailable`, **재시도 가능**) | 5xx, 429, 408, 제한 시간 초과, 연결 실패 |
| `AIRequestRejectedError` (`ai_request_rejected`, 재시도 불가) | 400, 401, 403, 404 등 |
| `AIResponseError` (`ai_response_invalid`, 재시도 불가, `reason`) | 프롬프트 차단, 안전 필터로 잘림, 빈 응답 |

## 기술 결정
- **키가 없어도 앱과 테스트는 시작된다.** 키 확인은 첫 호출 시점에 한다(`AINotConfiguredError`). 키가 필요 없는 엔드포인트가 AI 설정 때문에 뜨지 못하는 일이 없다.
- 모든 AI 오류는 `DomainError`의 하위 클래스이고 메시지는 학습자용 한국어다("AI 서비스가 응답하지 않습니다. 잠시 후 다시 시도하거나…"). **업스트림 오류 문구는 메시지에 넣지 않고** `__cause__`에만 둔다(내부 정보가 섞일 수 있다).
- **프롬프트, 응답, 키는 로그에 남기지 않는다.** 프롬프트는 학습자의 코드다. 실패 로그에는 모델, 상태 코드, 오류 종류만 남고, 테스트가 이를 확인한다.
- 버그(예: `ValueError`)와 작업 취소(`CancelledError`)는 AI 오류로 위장하지 않고 그대로 전파한다.
- 제한 시간은 호출마다 지정할 수 있다(문서 생성은 길게, Q&A는 FR-087의 10초에 맞춰 짧게).
- `thinking_tokens`를 응답에 노출한다(아래 발견 2 참고).

## 발견한 것
1. **테스트로 새는 실제 키**: `alembic/env.py`가 import될 때 `load_dotenv(.env)`를 호출해 `.env`의 모든 값을 프로세스 환경에 올린다. DB 테스트가 마이그레이션을 실행한 뒤에는 개발자의 **실제 `GOOGLE_API_KEY`가 환경에 남아 이후 테스트가 그 키를 보게 된다.** 이번 작업의 "키 없음" 테스트가 전체 실행에서만 실패해서 드러났고, 실패 로그의 `status=400`은 가짜 키로 실제 Google 서버에 요청이 나갔다는 증거였다. 진짜 키였다면 단위 테스트가 실제 호출을 했을 것이다. `conftest.py`의 공통 장치가 매 테스트 전에 `GOOGLE_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`를 환경에서 지우도록 고쳤다. conftest를 빼고(`--noconftest`) 키를 넣으면 테스트 2개가 실패함도 확인했다. 이 장치는 이후 다른 비밀 값에도 같은 문제가 있음을 알려 준다(JWT 비밀키 등도 같은 경로로 환경에 올라온다. 이번에는 AI 설정만 막았다).
2. **`max_output_tokens`는 생각 토큰을 포함한다**(gemini-3-flash-preview 실측): "1+1은? 숫자만 답하세요."에도 생각에 약 67토큰이 든다. `max_output_tokens=50`이면 생각이 46토큰을 쓰고 한도가 끝나 **텍스트 없이** `MAX_TOKENS`로 끝난다(200 이상이면 정상). 래퍼는 이를 `AIResponseError(reason="MAX_TOKENS")`로 알린다. 문서 생성(T093)은 한도를 크게 잡거나 아예 지정하지 말아야 한다. `generate()`의 문서에 적었다.

## 비고
- 재시도, 대기열, "재시도 중..." 안내(FR-088~FR-094)는 이 작업에 없다. T093(문서 생성 서비스)과 Q&A 구현에서 `retryable`을 보고 처리한다.
- API 오류 응답 표(`DOMAIN_ERROR_STATUS`)에는 AI 코드를 아직 넣지 않았다. 처리되지 않은 코드는 지금 400이 된다. AI를 부르는 엔드포인트를 만들 때 `ai_unavailable`은 503 계열, `ai_request_rejected`와 `ai_response_invalid`는 502 계열, `ai_not_configured`는 503으로 매핑해야 한다.
- `.env`는 `.gitignore`에 들어 있어 실제 키가 커밋되지 않는다(이 폴더는 git 저장소도 아니다). `.env.example`의 `GOOGLE_API_KEY`는 자리표시자다.
- 응답이 중간에 잘려도(`MAX_TOKENS`, 텍스트 있음) 예외로 만들지 않고 `finish_reason`으로 알린다. 잘린 JSON이 유효한지는 호출하는 쪽이 판단한다.
- 클라이언트는 `google-genai` 2.33.0 기준으로 확인했다. `requirements.txt`에는 `>=1.0`으로 적혀 있어 그대로 두었다.
