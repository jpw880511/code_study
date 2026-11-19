# TASK-094: 문서 생성 Celery 작업

## 상태
완료 (실제 워커+Redis 통합 검증은 별도로 필요)

## 날짜
2026-11-18

## 작업 요약
`DocumentGenerationService`(T093)로 Task의 학습 문서를 만드는 Celery 작업 `document_generation.generate`를 만들었다. 작업은 동기 함수이고 안에서 `asyncio.run`으로 비동기 서비스를 돈다.
- 흐름: 대기열에서 문서 선점(`start`) → 저장된 코드 읽기 → 문서 생성 → `completed`/`failed` 저장 → 재시도 안내 삭제.
- **실행마다 새 엔진/세션 팩토리**를 만들고 끝나면(예외여도) `dispose()`한다. `lru_cache`된 `get_session_factory`는 쓰지 않는다.
- 사용자의 `in_progress`가 이미 3개면 `deferred`를 돌려주고, Celery `retry(countdown=15, max_retries=None)`로 15초 뒤 다시 시도한다(문서는 `pending` 유지).
- 시간 제한은 이 작업만 소프트 540초 / 하드 600초(전역 300초는 그대로). `acks_late=True`, `reject_on_worker_lost=True`.
- 실패 문구는 학습자용 한국어만 저장한다: `DomainError`(AI 오류 포함)는 그 `message`, 소프트 시간 초과는 전용 문구, 그 밖의 예외는 일반 문구. 로그에는 작업 id, 예외 종류, 상위 상태 코드만 남긴다.
- `GeminiClient`, 재시도 안내 저장소, `sleep`을 주입할 수 있다(`run_generate_document`, `generate_for_task`).

## 워커 실행법
Redis는 `docker compose up -d`로 켠 뒤, `backend` 폴더에서(Windows):
```
celery -A src.tasks.celery_app worker -Q document_generation --pool=solo -l info
```
`celery_app`의 `include`에 작업 모듈이 들어 있어 워커가 작업을 스스로 찾는다. `.env`에 `GOOGLE_API_KEY`, `DATABASE_URL`, `REDIS_URL`이 필요하다.

## 변경 파일
- `backend/src/tasks/document_generation.py` (신규): `generate_document`, `generate_for_task`, `run_generate_document`, `enqueue_generation`
- `backend/src/tasks/celery_app.py`: `include=["src.tasks.document_generation"]`, `broker_transport_options.socket_connect_timeout=3`
- `backend/tests/integration/test_document_generation_task_db.py` (신규, 16개), `test_document_task_runner_db.py` (신규, 3개)
- `backend/tests/unit/test_document_celery_task.py` (신규)
- `backend/tests/conftest.py`: 자동 적용 `sent_jobs` 장치(브로커 전송을 가짜로 대체)
- `backend/tests/integration/conftest.py`, `backend/tests/queue_helpers.py` (신규 도우미)

## TDD 결과
- RED: 모듈이 없어 수집 단계에서 실패.
- GREEN: 같은 작업 2번 실행 시 한 번만 생성, 동시 4개 실행 시 한 번만 생성, 6개 문서 동시 실행 시 정확히 3개만 진행, 재시도 안내가 Redis에 들어갔다가 지워짐, 실패 문구, 코드 조각(비밀 문자열)이 `generation_error`와 로그에 없음, 소프트 시간 초과, 휴지통 Task, 파일 소실, 늦게 온 결과가 이미 failed인 문서를 덮어쓰지 않음, 실행마다 엔진 생성·dispose, 예외 때도 dispose.
- 실제 Celery 워커, Redis, Gemini는 사용하지 않았다.

## 기술 결정
- 작업 결과 문자열(`completed`/`failed`/`skipped`/`deferred`)로 흐름을 나눠 작업 본체를 일반 함수로 테스트한다. 브로커 호출(`apply_async`)은 가짜로 바꾼다.
- 전송은 작업 id(`task_id=job_id`)를 문서 행에 미리 저장한 값으로 지정한다(전송 시점에 DB 쓰기 불필요).
- 브로커가 죽었을 때 요청이 오래 붙잡히지 않도록 `retry_policy`(최대 1회)와 소켓 연결 제한 3초를 두었다.

## 비고 (알려진 한계, 계약과 다른 점)
- `--pool=solo`는 Celery 시간 제한(소프트/하드)을 **적용하지 않는다**. Windows 개발 환경에서는 제한이 동작하지 않으므로 15분 오래된 `in_progress` 정리가 안전망이다. 리눅스 prefork 풀에서 실제로 확인해야 한다.
- 워커가 죽어 같은 작업이 재전달되면 문서가 `in_progress`로 남아 있어 `skipped`가 되고, 15분 뒤 `failed`로 정리된다(자동 재생성은 하지 않는다. 동시 중복 방지를 우선).
- `pending`인 채 큐 메시지가 사라진 문서(브로커 데이터 유실)는 계속 `pending`이다. 계약은 `in_progress`만 정리하도록 요구한다.
- `deferred` 재시도는 `max_retries=None`이다. 사용자 슬롯은 정리 규칙 덕분에 결국 비워진다.
- 긴 작업을 위해 `worker_prefetch_multiplier=1`이 바람직하지만 전역 설정이라 바꾸지 않았다.
- 생각 토큰 한계(TASK-091), 부분 수락/템플릿 문서 미구현(TASK-093)은 그대로다.
- 실제 워커+Redis+Gemini로 한 번 끝까지 도는 검증은 하지 않았다.

## 통합 검증에서 확인한 것과 고친 것 (2026-11-19, 실제 Redis, Celery 워커, Gemini, 임시 DB)
에이전트가 하지 못한 실제 워커 검증을 컨트롤러가 직접 했다(워커는 `--pool=threads --concurrency=5`).

- **업로드 → 문서 완성**: 업로드 응답 0.1초(AI를 기다리지 않음), 상태 `pending` → `in_progress`(약 1초 뒤) → `completed`(약 22초). 문서에 7개 챕터가 모두 있고 내부 컬럼(`celery_task_id` 등)은 노출되지 않는다.
- **동시 3개 제한**: 한 사용자가 4개를 거의 동시에 요청하면 처음 3개가 동시에 돌고(폴링으로 본 최대 동시 `in_progress` = 3), 4번째는 `pending`으로 기다리다 앞 작업이 끝난 뒤 시작했다. 4개 모두 완료. 4번째는 앞 작업 완료 후 약 10초 뒤에 시작했다(15초 간격 재시도).
- **멈춘 문서 정리**: 16분 전에 시작한 `in_progress`를 조회하면 `failed`와 학습자용 문구로 바뀐다.
- **Redis가 꺼진 상태**: 업로드는 201, 문서는 즉시 `failed`("문서 생성 요청을 접수하지 못했습니다…"). Redis를 다시 켠 뒤 워커가 자동으로 재연결해 다음 작업이 정상 완료됐다(워커 로그의 "Connection to broker lost" 경고는 Celery의 정상 동작).
- **500줄(511줄) 코드**: 생성 25~26초, 난이도 advanced. FR-025의 3분 한도 안이다.
- **로그**: API 로그와 워커 로그에 학습자 코드 내용(표식 문자열)이 없다.
- **품질 재시도**: 한 번의 실제 생성에서 `calls=2`로 끝났다. 첫 응답이 검증을 통과하지 못해 수정 요청으로 다시 물은 뒤 성공했다(실제 모델에서 이 경로가 동작한다는 첫 증거).

### 발견해서 고친 결함: 워커 로그의 `Traceback`
- 증상: 문서 생성 1번마다 `Task exception was never retrieved ... AsyncClient.aclose() ... RuntimeError: Event loop is closed`가 로그에 남았다(6번 생성에 6번).
- 원인: `_run`이 작업마다 `GeminiClient()`를 만들지만 SDK의 비동기 HTTP 연결을 닫지 않은 채 `asyncio.run`이 이벤트 루프를 닫는다. 이후 가비지 컬렉션 때 SDK가 `aclose()`를 예약하는데 루프가 이미 닫혀 실패한다. 로그 소음일 뿐 아니라 연결 누수다.
- 수정(TDD, 테스트 먼저 RED 확인): `GeminiClient.aclose()` 추가(두 번 불러도 안전, 호출한 적 없으면 SDK를 만들지 않음, 닫은 뒤 다시 쓰면 새 SDK 클라이언트), `_run`이 **자기가 만든** 클라이언트만 이벤트 루프가 끝나기 전에 닫는다(호출자가 넘겨준 클라이언트는 닫지 않음, 작업이 깨져도 닫음). 테스트 6개 추가.
- 결과: `Traceback` 6회 → 0회(남은 1회는 위의 Redis 연결 끊김에 대한 Celery 자체 경고).

### 알려진 한계 (실제 측정으로 확인)
- **429(요청 과다)**: 같은 날 실제 호출을 많이 한 뒤 Gemini가 429를 연달아 돌려줘, 서비스 재시도 4번(2·4·8초 대기, 약 14초)이 모두 실패하고 문서가 `failed`가 된 일이 두 번 있었다. 화면에는 한국어 오류 문구가 정상으로 표시됐다. 몇 분 뒤에는 다시 성공했다. 재시도 대기(약 14초)가 분당 한도에는 짧다. FR-097이 말한 "한도 감지 시 60초 동안 새 요청 중단(큐 일시 정지)"은 구현되어 있지 않다.
- **추정 시간이 과대**: `estimated_total_seconds`는 511줄에서 131초였는데 실제는 25초였다(13~29줄은 20초 추정에 실제 18~22초로 맞았다). 공식(`15 + 0.25 × 줄 수`)이 줄 수에 너무 민감하다. 모델 응답 시간이 줄 수와 크게 비례하지 않았다.
- **4장이 코드를 거의 덮지 않는다**: 511줄 코드에서 4장 항목은 6개, 덮은 줄은 9줄뿐이었다(1.8%). 검증기는 줄 번호가 범위 안인지만 보고 얼마나 덮는지는 보지 않는다. "줄별 설명"(FR-031)이 큰 코드에서는 사실상 요약이 된다.
- **Windows `--pool=solo`/`threads`** 에서는 Celery 시간 제한(소프트 540초/하드 600초)이 적용되지 않는다. 15분 정리가 안전망이다. prefork 풀(리눅스)에서의 동작은 확인하지 못했다.
