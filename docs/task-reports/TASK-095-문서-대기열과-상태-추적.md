# TASK-095: 문서 대기열과 상태 추적

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
`DocumentQueueService`: 학습 문서의 상태 전환이 일어나는 **유일한 곳**.
- `register`: Task 생성 트랜잭션 안에서 `pending` 행을 만들고 `celery_task_id`(미리 만든 UUID)를 저장.
- `start`: `pending`→`in_progress`를 조건부 UPDATE로 한 호출만 성공시킨다. 사용자별 `pg_advisory_xact_lock`으로 "개수 확인 후 선점"이 동시에 일어나도 3개를 넘지 않게 한다. 이미 3개면 `DEFERRED`, 이미 끝났거나 다른 곳이 가져갔으면 `SKIPPED`.
- `complete`/`fail`/`fail_unsent`: 각각 `in_progress`/`in_progress`/`pending`일 때만 바뀐다(완료된 문서를 덮어쓰지 않음).
- 15분 넘은 `in_progress`는 `start`와 `get`에서 `failed`(학습자용 문구)로 정리. 시계를 주입할 수 있다.
- `describe`: 상태 응답. `elapsed_seconds`는 `in_progress`일 때만 서버가 계산, `estimated_total_seconds = min(180, max(20, round(15 + 0.25×total_lines)))`는 `pending`/`in_progress`일 때만, `notice`도 그때만, `error`는 `failed`일 때만.
- `NoticeStore`(재시도 안내): Redis에 Task별 키, TTL 300초. Redis 클라이언트 주입 가능, 모든 Redis 오류는 조용히 무시(오류 종류만 로그). `DocumentDispatcher`: 아래 T096.
- `DocumentNotFoundError`(`document_not_found`) 추가.

## 변경 파일
- `backend/src/services/document/document_queue_service.py` (신규)
- `backend/src/services/document/document_notice_store.py` (신규)
- `backend/src/services/document/errors.py` (`DocumentNotFoundError` 추가)
- `backend/tests/integration/test_document_queue_service_db.py` (신규, 19개), `backend/tests/unit/test_document_notice_store.py`, `test_document_estimate.py` (신규)

## TDD 결과
- RED: 모듈이 없어 수집 단계에서 실패.
- GREEN: 한도 3개(다른 사용자는 세지 않음, 슬롯이 비면 시작), 오래된 상태 정리(정확히 15분은 정리하지 않음), 중복 시작 거부, 완료 문서 보호, 상태 응답 모양, 추정 시간 식, 안내 저장/TTL/Redis 장애 무시를 테스트로 고정.

## 기술 결정
- 서비스는 커밋하지 않는다(기존 패턴). 워커는 `start` 직후 직접 커밋해 자문 잠금을 푼다.
- 상태 읽기마다 "오래된 것 정리" UPDATE가 한 번 돈다. 해당 행이 없으면 쓰기가 일어나지 않는다.
- 계약의 `notice`는 RetryEvent 대신 완성된 문구를 Redis에 저장한다(같은 결과, 읽는 쪽이 단순).

## 비고
- 계약 3장의 "큐에 못 보내도 문서는 failed" 처리를 위해 `fail_unsent`를 따로 두었다(진행 중인 문서는 건드리지 않는다).
- `pending` 문서의 유실(브로커 데이터 소실)은 정리하지 않는다(TASK-094 비고).
- 실제 Redis에서의 동작은 확인하지 않았다(가짜 클라이언트로만 테스트).
