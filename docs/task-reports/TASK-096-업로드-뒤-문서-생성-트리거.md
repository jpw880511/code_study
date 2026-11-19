# TASK-096: 코드 업로드 뒤 문서 생성 트리거

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
Task를 올리면 문서 생성이 **커밋된 뒤에만** 큐에 들어간다.
- `CodeUploadService.create_task`가 Task 생성 트랜잭션 안에서 `pending` 문서 행을 만든다(Task와 함께 커밋되거나 함께 사라짐). `UploadResult.document_job_id`로 작업 id를 돌려준다. 응답 모양은 바뀌지 않는다.
- `POST /projects/{id}/tasks` 핸들러가 FastAPI `BackgroundTasks`로 `DocumentDispatcher.dispatch`를 등록한다. 백그라운드 작업은 응답이 나갈 때 시작되므로, `DbSession`(`scope="function"`)이 커밋한 뒤이고, 핸들러나 커밋이 실패하면 아예 실행되지 않는다.
- `DocumentDispatcher`는 브로커 호출(blocking)을 스레드에서 실행한다. 보내지 못하면 오류 종류만 로그에 남기고 문서를 `failed`(`fail_unsent`, 학습자용 문구)로 만든다. 업로드는 그대로 201이다.
- `get_document_dispatcher` 의존성이 기본 전송 함수와 앱 세션 팩토리를 연결한다.
- 기존 테스트가 실제 브로커를 건드리지 않도록 `tests/conftest.py`에 자동 적용 장치(`sent_jobs`)를 넣어 `enqueue_generation`을 기록용 가짜로 바꿨다.

## 변경 파일
- `backend/src/services/code_analysis/code_upload_service.py` (문서 행 등록, `UploadResult.document_job_id`)
- `backend/src/services/document/document_dispatcher.py` (신규)
- `backend/src/api/tasks.py`, `backend/src/api/dependencies.py` (`Dispatcher`, `get_document_dispatcher`)
- `backend/tests/conftest.py` (자동 가짜 브로커)
- `backend/tests/integration/test_document_trigger_db.py` (신규, 4개), `test_document_dispatcher_db.py` (신규, 5개)

## TDD 결과
- RED: 모듈이 없어 수집 단계에서 실패.
- GREEN(증명한 것): (1) **커밋 전에는 안 나간다**: 전송 함수 안에서 다른 DB 연결로 조회하면 `pending` 행이 보이고 작업 id가 같다. 핸들러 안에서 바로 보내도록 바꿔 보면 이 테스트가 실패한다(변이 확인). (2) **롤백이면 안 나간다**: 검증 실패(422)와, 문서 행을 만든 뒤 응답 생성이 터지는 500 모두 전송 0건, 문서·Task 행 0개. (3) **브로커가 죽어도 업로드 성공**: 201, 이후 상태 조회는 `failed`와 학습자용 문구이고 접속 URL이 새지 않는다. 마킹 자체가 실패해도 예외가 밖으로 나가지 않는다.

## 기술 결정
- 큐 전송 id를 행에 미리 저장해 전송 뒤에 DB를 다시 쓰지 않는다(실패 경로만 새 세션).
- 기존 `test_tasks_api_*`, `test_code_upload_service_db.py`는 수정하지 않았다. 문서 행이 하나 더 생기지만 기존 단언은 그대로 통과한다.

## 비고
- 커밋은 성공했는데 전송 직전에 서버 프로세스가 죽으면 문서는 `pending`으로 남는다(재전송 장치 없음). 후속 과제.
- 기본 전송은 `to_thread`로 도는 동기 Celery 호출이다. 실제 Redis가 죽은 상태에서 걸리는 시간은 실측하지 못했다(설정상 연결 3초, 재시도 1회).
