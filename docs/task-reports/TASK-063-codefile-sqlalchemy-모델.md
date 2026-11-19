# TASK-063: CodeFile SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
`code_files` 테이블에 대응하는 `CodeFile` 모델을 만들었다. 업로드된 코드(UploadedCode) 안의 파일 하나를 설명하며(이름, 상대 경로, 확장자, 크기, 저장 경로, MIME 타입), 마이그레이션(T009)의 컬럼·제약·인덱스 이름을 그대로 따른다. `UploadedCode.code_files` ↔ `CodeFile.uploaded_code` 관계를 연결했다.

## 변경 파일
- `backend/src/models/code_file.py` (신규)
- `backend/src/models/__init__.py` (`CodeFile` 내보내기)
- `backend/src/models/uploaded_code.py` (`UploadedCode.code_files` 관계 추가, 주석 정리)
- `backend/tests/unit/test_code_file_model.py` (신규, 메타데이터 검증)
- `backend/tests/integration/test_code_file_model_db.py` (신규, 실제 DB 검증)

## TDD 결과
- RED: `CodeFile`이 없어 두 테스트 파일 모두 수집 단계에서 실패.
- GREEN: 신규 46개 통과. 전체 710개 통과(건너뜀 0), 커버리지 100%(859문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 검증한 규칙: 지원 확장자 12개는 모두 허용, `.exe`·`.PY`(대문자)·`py`(점 없음)·`.pyc`·`.zip`·빈 문자열은 거부(`supported_extension`), `file_name`(255자 한도)·`storage_path`·`uploaded_code_id` 필수, 존재하지 않는 업로드 참조 거부, 한 업로드에 같은 이름의 파일 여러 개 허용(폴더가 다르면 가능), 업로드·프로젝트 삭제 시 DB가 파일 행을 연쇄 삭제, 모델이 실제 마이그레이션된 스키마와 일치.

## 기술 결정
- 지원 확장자 12개를 `SUPPORTED_EXTENSIONS` 튜플로 노출하고, 모델의 CHECK 제약 문자열을 이 튜플에서 만든다. T064(파일 검증 유틸)가 같은 튜플을 쓰면 코드와 DB 규칙이 어긋나지 않는다. 테스트는 튜플의 내용을 명세의 12개와 직접 비교하고, 실제 DB의 제약에도 12개가 모두 있는지 확인한다.
- 이름 있는 제약 `supported_extension`은 `conv()`로 DB 이름을 그대로 유지한다.
- 유니크 제약은 두지 않는다(마이그레이션과 동일). 같은 업로드 안에서 같은 이름·다른 경로의 파일이 가능해야 하기 때문이다.
- 관계는 `lazy="raise"`, `passive_deletes=True`로 기존 모델과 같은 규칙을 따른다.
- `__repr__`에는 ID만 넣고 파일 이름과 경로는 넣지 않는다(사용자 코드 정보가 로그에 남지 않도록).

## 비고
- 확장자 CHECK는 NULL을 통과시킨다(SQL 표준 동작). 확장자 없는 파일(`Makefile` 등)의 거부는 모델이 아니라 T064의 검증이 맡는다. 통합 테스트가 이 동작을 명시적으로 문서화한다.
- 확장자는 소문자만 허용된다. 대문자 확장자(`.PY`)를 받으려면 T064에서 소문자로 정규화한 뒤 저장해야 한다.
- 파일 내용은 DB가 아니라 디스크의 `storage_path`에 저장된다(T067).
- `ruff format --check`의 기존 지적(`tests/unit/test_token_service.py`)은 이번 작업과 무관하다.
