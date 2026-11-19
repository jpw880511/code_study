# TASK-075. GET /tasks/{task_id}/code 엔드포인트

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
저장된 코드 파일의 내용을 돌려준다. `GET /api/v1/tasks/{task_id}/code` → `200 CodeResponse` = `{"files": [...]}`.
- 각 파일은 `CodeFileSummary` 필드 + `language`(파일별 감지 언어, 모르면 `"unknown"`) + `content`(UTF-8, 잘못된 바이트는 대체 문자).
- 정렬은 `file_path`(없으면 `file_name`) 오름차순.
- 오류: 업로드가 없는 Task는 404 `code_not_found`("이 Task에는 업로드된 코드가 없습니다."), 디스크에서 파일이 사라졌거나 저장된 경로가 저장 루트 밖이면 404 `code_file_missing`("저장된 코드 파일을 찾을 수 없습니다."). 소유권·휴지통 규칙은 Task와 같다(남의 것 403, 휴지통·없는 것 404).

## 변경 파일
- `backend/src/api/tasks.py` (`get_task_code`), `backend/src/api/task_schemas.py` (`code_response`)
- `backend/tests/integration/test_tasks_api_db.py`, `backend/tests/integration/test_code_upload_service_db.py`

## TDD 결과
- RED: 라우트 없음.
- GREEN: 통과. 폴더 업로드 두 파일이 경로순(`app/a.js`, `app/b.py`)으로 나오고 언어가 `javascript`/`python`, 내용 일치, 응답 키 집합이 계약과 일치(내부 키 없음), `file_size_bytes`가 내용의 UTF-8 바이트 수와 같음, 업로드 없는 Task `code_not_found`, 파일 삭제 후 `code_file_missing`, DB의 `storage_path`를 `../../etc/passwd`로 바꿔도 읽지 않고 `code_file_missing`, 잘못된 UTF-8(`\xb0\xa1`)은 `�`로 치환, 휴지통 Task 404.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 파일 하나라도 없으면 부분 응답 없이 404 `code_file_missing`으로 끝낸다(문서 생성이 일부 코드만 보고 진행하지 않도록).
- 파일 읽기는 `asyncio.to_thread`로 이벤트 루프를 막지 않는다.
- 언어는 저장된 값이 아니라 읽을 때 `detect_language(경로 또는 이름, 내용)`로 구한다(계약).

## 비고
- 응답 크기는 10MB 업로드 한도에 비례해 클 수 있다. 스트리밍·페이지네이션은 계약에 없어 넣지 않았다.
- CP949 같은 기존 인코딩 파일은 대체 문자로 보인다(업로드는 허용하지만 UTF-8만 해석). 인코딩 감지는 후속 과제다.
