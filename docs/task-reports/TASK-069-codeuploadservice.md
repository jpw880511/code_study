# TASK-069. CodeUploadService (파일·폴더·붙여넣기 업로드)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
Task와 업로드 코드를 한 번에 만드는 `CodeUploadService.create_task`와, 저장된 코드를 읽는 `read_code`를 만들었다.
- **검사 순서**(계약): 프로젝트 소유권 → 업로드 방식 → 제목 → 설명 → (paste) 언어/빈 코드 또는 (file·folder) 경로 정규화 → 제외 → 개수(1~20) → 파일별 `validate_file`(확장자→크기→바이너리) → 합계 10MB. 이 모든 검사가 끝나기 전에는 DB·디스크에 아무것도 쓰지 않는다.
- **file**: 이름은 마지막 구성요소만 사용(`paths` 무시). **folder**: `paths`는 `files`와 개수가 같아야 하며(아니면 `invalid_file_path`), 절대 경로·`..`·`.`·빈 세그먼트·역슬래시·콜론·제어 문자·255자 초과 세그먼트를 거부한다. `.git`, `node_modules`, `__pycache__` 디렉터리나 `.DS_Store` 파일은 제외하고 `excluded_paths`에 담는다(제외 파일은 읽지도, 검증하지도, 개수에 세지도 않는다). 제외 후 0개면 `no_files`.
- **paste**: 언어 드롭다운 10개 값만 허용(`language_required`/`unsupported_language`/`empty_code`), `pasted_code<확장자>` 파일 1개를 만든다. 크기·바이너리 검사도 적용.
- **분석**: 파일별 언어(`detect_language`/붙여넣기는 선택 언어), 복잡도(`assess`), `total_lines`, `total_files`, `upload_size_bytes`. 대표 언어는 코드 파일의 언어별 줄 수 합이 가장 큰 언어(동률은 먼저 올라온 쪽), 코드가 없으면 문서 중, 전부 unknown이면 `unknown`. 코드 줄 수 500 초과 시 `large_code` 경고.
- **원자성**: DB 쓰기를 savepoint(`begin_nested`)로 감싸고, 어떤 단계에서든 실패하면 저장한 파일과 Task 폴더를 지운다.
- **메모리 보호**: 파일당 최대 `MAX_UPLOAD_SIZE_BYTES + 1`바이트만 읽는다.
- `read_code`: 소유권·휴지통 규칙은 `TaskService.get`을 따르고, 파일은 경로·이름 오름차순, 내용은 UTF-8(잘못된 바이트는 대체 문자), 언어는 파일별 감지(모르면 `unknown`). 업로드가 없으면 `code_not_found`, 디스크에 없으면 `code_file_missing`.

## 변경 파일
- `backend/src/services/code_analysis/code_upload_service.py`, `backend/src/services/code_analysis/upload_errors.py` (신규)
- `backend/tests/unit/test_upload_rules.py` (신규, 49개: 경로 정규화·제외·대표 언어·상수)
- `backend/tests/integration/test_code_upload_service_db.py` (신규, 78개)

## TDD 결과
- RED: 모듈이 없어 수집 단계 `ModuleNotFoundError`.
- GREEN: 신규 127개 통과. 확인한 것: 검사 순서, 붙여넣기 10개 언어, 폴더 제외(제외 파일은 `read`가 한 번도 호출되지 않음), 20개/21개 경계, 정확히 10MB 허용, 10MB 초과 파일은 정확히 `MAX+1`바이트만 읽음, 합계 초과, **디스크 쓰기가 3번째 파일에서 실패해도 파일·폴더·행이 모두 남지 않음**, **파일을 쓴 뒤 DB flush가 실패해도 파일이 지워짐**, 실패 뒤 다음 Task 번호가 다시 1, 검증 실패 시 아무것도 남지 않음(행·파일·폴더·프로젝트 활동 시각), 사용자 경로가 디스크 경로에 쓰이지 않음, 저장된 경로가 루트 밖을 가리키면 `code_file_missing`.
- 전체: 통과, skip 0, 커버리지 100%, ruff/mypy 통과.

## 기술 결정
- 업로드 파일은 `IncomingFile(name, source)`로 받는다. `source`는 `async read(size)`만 있으면 되므로(Starlette `UploadFile` 포함) 서비스가 HTTP를 모르는 채로 지연 읽기가 가능하다. 파일 수·확장자를 먼저 검사해 불필요한 읽기를 피한다.
- MIME 타입은 `mimetypes` 대신 고정 표를 쓴다(운영체제 레지스트리에 따라 결과가 달라지지 않도록).
- 붙여넣기 언어 값은 `normalize_language` 결과와 같은 이름이라(테스트로 고정) 그대로 쓴다.
- 대표 언어는 파일 하나가 아니라 **언어별 줄 수 합**으로 정한다(계약의 "줄 수가 가장 많은 언어").

## 비고
- **계약 해석**: "코드 파일이 없으면 전체 중 가장 많은 언어, 전부 unknown이면 unknown"에서 unknown은 다른 언어가 있으면 후보에서 뺀다. 지원 확장자만 허용하므로 실제로 unknown이 나오는 경우는 거의 없다.
- **검사 순서의 미세한 차이**: 읽은 파일의 누적 크기가 10MB를 넘으면 이후 파일을 읽지 않고 바로 합계 초과(`file_too_large`)로 응답한다(메모리 보호). 이후 파일에 별도 오류(확장자 등)가 있어도 합계 오류가 먼저 나간다.
- 단일 파일 업로드에서 파일명에 디렉터리가 섞여 오면 마지막 구성요소만 쓴다(계약은 이 경우를 정하지 않음). 이름이 비거나 255자를 넘거나 제어 문자가 있으면 `invalid_file_path`.
- DB 커밋 자체가 실패하는 경우의 고아 파일은 TASK-067 비고 참조.
