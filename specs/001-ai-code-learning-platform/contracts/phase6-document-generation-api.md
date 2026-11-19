# Phase 6 계약: 학습 문서 생성 (T094–T108)

백엔드(T094–T098)와 프론트엔드(T099–T108)가 **동시에** 개발하므로 이 문서가 둘 사이의 유일한 약속이다.
서로의 코드를 기다리지 말고 이 문서만 보고 구현한다. 문서와 다르게 만들어야 할 이유를 발견하면 구현을 바꾸지 말고 보고한다.
이 문서가 말하지 않는 것은 `contracts/phase5-tasks-upload-api.md`(오류 형식, 인증, 규칙)를 따른다.

## 0. 전체 흐름

1. 사용자가 Task를 올린다(`POST /projects/{id}/tasks`, 기존 API). **응답은 바뀌지 않는다.**
2. Task가 **커밋된 뒤에** 문서 생성이 큐에 들어간다(상태 `pending`). 업로드는 AI나 Redis 상태와 무관하게 성공한다.
3. Celery 워커가 `DocumentGenerationService`(T093)로 문서를 만들고 `learning_documents`에 저장한다(`in_progress` → `completed` 또는 `failed`).
4. 프론트엔드가 상태를 폴링하다가 완료되면 문서를 불러와 코드와 설명을 나란히 보여 준다.

이미 있는 재료(다시 만들지 말 것): `DocumentGenerationService`, `validate_document`, `GeneratedDocument`, `RetryEvent`, `DocumentGenerationError`, `GeminiClient`, `LearningDocument` 모델(`empty_content()`, `CHAPTER_KEYS`, `GENERATION_STATUSES`), `CodeUploadService.read_code`, `TaskService`, `FileStorage`, `celery_app`(큐 `document_generation`이 이미 정의됨).

## 1. API (모두 `/api/v1`, 쿠키 인증, 오류 형식은 기존과 같다)

### GET /tasks/{task_id}/document/status → 200
```json
{
  "status": "pending | in_progress | completed | failed",
  "generation_started_at": "2026-11-18T09:00:00Z 또는 null",
  "generation_completed_at": "… 또는 null",
  "elapsed_seconds": 12,
  "estimated_total_seconds": 22,
  "notice": "AI 서비스가 바빠 다시 시도하는 중입니다 (1/3). 또는 null",
  "error": "문서를 만들지 못했습니다. … 또는 null"
}
```
- `elapsed_seconds`: **서버가 응답 시점에 계산**한 경과 시간(`in_progress`일 때만, 아니면 null). 브라우저와 서버 시계가 달라도 남은 시간을 맞게 보여 주려는 것이다.
- `estimated_total_seconds`: `pending`/`in_progress`일 때만 숫자, 아니면 null. 대략적인 추정이다: `min(180, max(20, round(15 + 0.25 × uploaded_code.total_lines)))` (13~29줄에서 실측 18~22초, FR-025 한도 180초).
- `notice`: 워커가 재시도 사이에 기다리는 동안의 안내 문구(아래 4번). 없으면 null.
- `error`: `failed`일 때만 학습자용 한국어 문구, 아니면 null. **원문 예외, 프롬프트, 코드는 절대 담지 않는다.**

### GET /tasks/{task_id}/document → 200
```json
{
  "task_id": "uuid",
  "status": "pending | in_progress | completed | failed",
  "content": null,
  "generation_started_at": null,
  "generation_completed_at": null,
  "error": null,
  "created_at": "…",
  "updated_at": "…"
}
```
- `content`: **`completed`일 때만** 7개 챕터 객체(2번), 그 밖에는 `null`(대기·진행·실패 때의 빈 챕터 자리표시자를 내보내지 않는다).
- 응답에 `celery_task_id`, `storage_path`, 내부 컬럼을 넣지 않는다.

### 오류
| HTTP | error | message |
|---|---|---|
| 401 | `not_authenticated` | (기존) |
| 404 | `task_not_found` | (기존) 휴지통 Task, 휴지통 프로젝트의 Task 포함 |
| 403 | `task_forbidden` | (기존) 남의 Task |
| 404 | `document_not_found` | 이 Task에는 아직 학습 문서가 없습니다. |

- `document_not_found`는 문서 행이 없을 때다(Phase 6 이전에 만든 Task, 큐에 넣지 못한 Task). 상태 엔드포인트와 문서 엔드포인트가 같게 응답한다.
- 문서 생성을 시작하거나 다시 시작하는 엔드포인트는 **이번 범위에 없다**(자동 시작만).

## 2. `content`의 구조 (이미 확정, `src/services/ai/prompts.py`의 `OUTPUT_SKELETON`이 원본)

| 챕터 | `title`(고정) | 필드 |
|---|---|---|
| chapter1 | 이 코드가 하는 일 | `summary` |
| chapter2 | 미리 알아야 할 지식 | `concepts[]`: `name`, `explanation`, `analogy`, `example`, `use_cases` (1~5개) |
| chapter3 | 코드 구조 한눈에 보기 | `flowchart`(텍스트 순서도), `file_breakdown`(경로 → 설명 객체) |
| chapter4 | 한 줄씩 설명 | `explanations[]`: `file`, `line_start`, `line_end`, `code`, `what_it_does`, `syntax_breakdown`, `analogy`, `alternatives`, `notes` |
| chapter5 | 실행 흐름 따라가기 | `steps[]`: `step`(1부터 순서), `description`, `data` |
| chapter6 | 핵심 개념 정리 | `concepts[]`: `name`, `what_it_is`, `why_its_used`, `where_its_applied` |
| chapter7 | 흔한 실수 | `mistakes[]`: `wrong`, `right`, `why`, `fix` (3~5개) |

- chapter4의 `file`은 업로드한 파일의 경로(`code_files.file_path`가 있으면 그것, 없으면 `file_name`)이고, `line_start`/`line_end`는 그 파일의 1부터 시작하는 줄 번호(양 끝 포함)다. 코드 패널의 줄 강조(FR-047)에 쓴다.
- chapter4가 **모든 줄을 덮는다는 보장은 없다**(알려진 한계). 화면은 설명이 없는 줄이 있어도 정상이어야 한다.
- 4장의 `analogy`, `alternatives`, `notes`, `syntax_breakdown`과 5장의 `data`는 빈 문자열일 수 있다.
- 모든 텍스트는 **일반 텍스트**다. 코드, HTML 태그, `<`가 들어 있을 수 있으므로 **어디서도 HTML로 렌더링하지 않는다**(`dangerouslySetInnerHTML` 금지).

## 3. 상태 규칙 (백엔드)

- `pending` = 큐에서 기다리는 중, `in_progress` = 워커가 만드는 중, `completed`, `failed`.
- **사용자당 동시에 만드는 문서는 최대 3개**(FR-086). 4번째부터는 거절하지 않고 `pending`으로 둔다(FR-088, 큐잉). 워커는 자기 차례에 그 사용자의 `in_progress`가 이미 3개이면 잠시 뒤(예: 15초) 다시 시도하는 방식으로 기다린다.
- **어떤 문서도 `in_progress`로 영원히 남아서는 안 된다.** 워커가 죽거나 시간이 지나친 경우: `generation_started_at`이 15분 넘게 지난 `in_progress`는 상태를 읽을 때(또는 작업이 시작될 때) `failed`로 바꾸고 학습자용 문구를 넣는다. 15분은 문서 생성 Celery 작업의 하드 시간 제한보다 길어야 한다.
- 실패하면 `failed` + `generation_error`(학습자용 한국어) + `generation_completed_at`. 문구는 `AIServiceError.message`/`DocumentGenerationError.message` 같은 서비스의 한국어 메시지를 쓰고, 예상 못 한 예외는 일반 문구("문서를 만드는 중 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도하거나 고객지원에 문의하세요.")를 쓴다. 원인(예외 종류, 상태 코드)은 서버 로그에만, **프롬프트와 코드 내용 없이** 남긴다.
- **중복 전달에 안전해야 한다**: 같은 작업이 두 번 실행되어도(Celery 재전달) 이미 `completed`인 문서를 다시 만들거나 덮어쓰지 않는다. `in_progress`로 만드는 전환은 조건부로(원자적으로) 해서 두 워커가 같은 문서를 동시에 만들지 못하게 한다.
- 상태 전환은 한 곳(`document_queue_service`)에서만 한다.
- 문서 행은 Task 생성 트랜잭션 안에서 `pending`으로 만든다(Task와 함께 커밋되거나 함께 사라진다). `completed`/`failed`가 된 뒤에는 다시 만들지 않는다.

## 4. 재시도 안내 (`notice`)

- `DocumentGenerationService`의 `on_retry` 콜백으로 받은 `RetryEvent`를 **Redis에 임시 저장**(키는 Task별, TTL 약 5분)하고 상태 엔드포인트가 읽는다. Redis가 없으면 `notice`는 null(조용히 실패, 상태 조회를 깨뜨리지 않는다).
- 문구: `service` 종류 → "AI 서비스가 바빠 다시 시도하는 중입니다 ({attempt}/{max_attempts})." / `quality` 종류 → "AI 응답을 다듬어 다시 요청하는 중입니다 ({attempt}/{max_attempts})."
- 완료·실패 때, 그리고 다음 안내가 오면 지운다.

## 5. 백엔드 구현 요구 (T094–T098)

- **T094** `src/tasks/document_generation.py`: Celery 작업. Celery 작업은 동기 함수이므로 안에서 `asyncio.run`으로 비동기 서비스를 돈다. **작업이 실행될 때마다 새 DB 엔진/세션 팩토리를 만들고 끝나면 닫는다**(`get_session_factory`는 `lru_cache`라 이벤트 루프가 다른 `asyncio.run` 호출 사이에서 재사용하면 깨진다). 큐는 `document_generation`. 이 작업만 시간 제한을 늘린다(전역 300초는 재시도까지 포함한 문서 생성에 짧다. 소프트 약 540초, 하드 약 600초). `acks_late`와 워커 소실 시 재전달을 설정하되 위 "중복 전달에 안전" 규칙을 지킨다.
- **T095** `src/services/document/document_queue_service.py`: 대기열 등록(문서 행 `pending` 생성, `celery_task_id` 저장), 상태 전환(시작·완료·실패), 사용자별 동시 3개 확인, 오래된 `in_progress` 정리, 재시도 안내 저장/조회, 상태 응답용 추정 시간 계산.
- **T096** 업로드 뒤 트리거: **커밋된 뒤에만** 큐에 보낸다. 요청이 롤백되면(검증 실패 등) 보내지 않는다. 큐에 못 보내도(Redis 다운) 업로드는 성공하고 문서는 `failed`(학습자용 문구)로 남는다. 현재 요청 세션은 `DbSession`(응답 전에 커밋)이므로, 보내는 시점을 이 흐름에 맞게 설계하고 테스트로 증명한다.
- **T097/T098** `src/api/documents.py`: 위 두 엔드포인트. 소유권·휴지통 규칙은 `TaskService.get` 한 곳을 재사용한다. 스키마는 `api/document_schemas.py` 등으로 분리해도 된다. `document_not_found`를 `DOMAIN_ERROR_STATUS`에 추가한다(404).
- AI 호출은 **테스트에서 절대 실제로 나가지 않는다**(가짜 클라이언트). conftest의 `GOOGLE_API_KEY` 제거 장치가 이미 있다. 워커 안에서 쓰는 `GeminiClient`는 주입 가능하게 만든다.
- 개발자용 실행법을 `docs/`가 아니라 작업 보고서(T094)에 적는다: Windows에서는 `celery -A src.tasks.celery_app worker -Q document_generation --pool=solo -l info`(backend 폴더에서), Redis는 `docker compose up -d`.

## 6. 프론트엔드 구현 요구 (T099–T108)

- **서비스(T106)** `src/services/document-service.ts`: 위 응답 타입(`DocumentStatus`, `DocumentStatusInfo`, `TaskDocument`, 챕터 타입)과 `getDocumentStatus(taskId)`, `getDocument(taskId)`. 훅은 `src/hooks/useDocument.ts`: 상태는 `pending`/`in_progress`일 때만 **2초마다 폴링**하고 `completed`/`failed`가 되면 멈춘다. `completed`가 되면 문서를 한 번 가져온다. `document_not_found`(404)는 오류가 아니라 "문서 없음" 상태다. 코드는 기존 `getTaskCode`(`GET /tasks/{id}/code`)를 쓰는 훅(`useTaskCode`)을 추가한다.
- **Monaco(T099)**: 에디터는 `src/components/document/CodeEditor.tsx` 같은 **얇은 래퍼 하나**에 가둬서 나머지 코드가 Monaco를 직접 알지 못하게 한다(jsdom에서는 Monaco가 동작하지 않으므로 테스트는 이 래퍼를 가짜로 바꾼다). 요구: CDN에서 불러오지 않는다(오프라인·CSP 안전, 번들에서 가져온다), **메인 번들에 넣지 않고 늦게 불러온다**(문서 탭을 열 때), 읽기 전용, 줄 번호 표시, 언어별 구문 강조(FR-042, FR-043), 특정 줄 범위 강조, 특정 줄로 스크롤, 보이는 첫 줄이 바뀔 때 알림. 빌드와 린트가 통과해야 한다.
- **CodePanel(T100)**: 파일이 여러 개면 파일 선택(탭), 선택한 파일의 코드를 `CodeEditor`로 보여 준다. 강조할 `{file, line_start, line_end}`를 받으면 그 파일로 바꾸고 그 줄로 스크롤한다.
- **ExplanationPanel(T101)**: 챕터 목록(1~7장) 탐색: 아무 장으로 바로 이동(비선형, FR-045), **지금 읽는 장 강조**(FR-044), 접근 가능한 마크업(`nav`, `aria-current`). 장 완료 표시(FR-046)는 진행률 API가 생기는 이후 단계의 일이라 **이번 범위가 아니다**.
- **챕터 컴포넌트**: T102 `Chapter1`, T103 `Chapter2`(개념 카드 최대 5개, 각 카드에 비유가 보인다), T104 `Chapter4`(줄별 설명: 항목을 누르거나 포커스하면 코드 패널에서 그 줄 범위를 강조하고 스크롤). 작업 목록에 없지만 문서 전체를 보여 주려면 필요하므로 `Chapter3`(순서도는 고정폭 텍스트, 파일별 설명), `Chapter5`, `Chapter6`, `Chapter7`도 **간단하게** 만든다.
- **DocumentViewer(T105)**: 데스크톱은 코드와 설명을 **나란히** 두 칼럼, 좁은 화면은 위아래로. **스크롤 동기화**(FR-041, FR-047): 코드 패널을 스크롤하면 설명 패널이 그 줄에 해당하는 4장 항목(줄 범위가 보이는 첫 줄을 포함하는 항목)으로 이동하고 그 항목을 강조, 설명의 항목을 선택하면 코드 패널이 그 줄을 강조한다. 서로의 스크롤이 서로를 되돌려 끝없이 반응하지 않게 한다.
- **로딩 상태(T107)**: `pending` → "문서 생성을 기다리는 중", `in_progress` → 진행 표시줄(`role="progressbar"`)과 **남은 시간 추정**("약 N초 남음", `estimated_total_seconds - elapsed_seconds`, 0 아래로 내려가지 않고 0이면 "곧 완료됩니다"), `notice`가 있으면 표시, `failed` → `error` 문구(다시 시작 버튼은 **없다**, 이번 범위 밖), 문서 없음 → "아직 학습 문서가 없습니다."
- **TaskDetail(T108)**: 문서 탭에 `DocumentViewer`를 넣는다. 두 칼럼이 들어가도록 문서 탭이 열려 있을 때는 페이지를 넓게(현재 `max-w-3xl`) 쓴다. 연습문제·Q&A 탭은 자리표시자 그대로.
- 접근성·한국어: 모든 화면 문구는 한국어, 역할/라벨을 명확히(이후 Playwright가 `getByRole`을 쓴다). 로딩·빈·오류 상태를 모두 구현.
- 이번 범위 밖: 장 완료 표시, 재생성 버튼, 연습문제·Q&A, 서버 쪽 코드 변환.
