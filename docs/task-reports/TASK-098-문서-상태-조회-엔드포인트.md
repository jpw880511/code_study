# TASK-098: GET /tasks/{task_id}/document/status

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
프론트엔드가 폴링하는 상태 엔드포인트. 응답은 계약 그대로 `status`, `generation_started_at`, `generation_completed_at`, `elapsed_seconds`, `estimated_total_seconds`, `notice`, `error` 7개 키.
- `elapsed_seconds`는 서버가 응답 시점에 계산(`in_progress`일 때만).
- `estimated_total_seconds = min(180, max(20, round(15 + 0.25 × total_lines)))`, `pending`/`in_progress`일 때만.
- `notice`는 Redis에서 읽는다(`pending`/`in_progress`일 때만). Redis가 꺼져 있거나 오류여도 200이고 `notice`는 `null`이다. Redis 연결 제한 1초.
- `error`는 `failed`일 때만 학습자용 한국어 문구.
- 오류 코드는 T097과 같다. 요청마다 만든 Redis 클라이언트는 응답 뒤 닫는다(`get_notice_store`).

## 변경 파일
- `backend/src/api/documents.py`, `backend/src/api/document_schemas.py`, `backend/src/api/dependencies.py` (`get_notice_store`, `Notices`)
- `backend/tests/integration/test_documents_api_db.py`

## TDD 결과
- RED: 엔드포인트가 없어 실패.
- GREEN: 업로드 직후 `pending`(추정 20초, 나머지 null), `in_progress`의 경과 시간(30초 전 시작 → 30~40초)과 안내문, Redis 장애 시 200+null, `failed`일 때 안내·추정·경과가 숨겨짐, 오래된 `in_progress`가 `failed`+정리 문구, `completed`에서 추정 null. 모든 테스트는 메모리 가짜 Redis만 쓴다.

## 비고
- 폴링(2초마다)마다 오래된 상태 정리 UPDATE 1회와 Redis GET 1회가 돈다. 규모가 커지면 캐시를 고려한다.
- 실제 Redis와의 연결(TTL 포함)은 직접 확인하지 못했다.
