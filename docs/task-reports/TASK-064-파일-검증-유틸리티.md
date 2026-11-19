# TASK-064: 파일 검증 유틸리티 (확장자, 크기, 바이너리 감지)

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
업로드된 파일을 저장·분석하기 전에 검사하는 순수 함수 모음을 만들었다. 확장자(FR-015), 크기 10MB(FR-014), 바이너리 거부(FR-016)를 검사하고, 거부 시 한국어 메시지·상세·해결 방법을 담은 `FileValidationError`를 던진다. DB나 파일시스템에 접근하지 않는다.

## 변경 파일
- `backend/src/utils/file_validator.py` (신규)
- `backend/tests/unit/test_file_validator.py` (신규, 67개)

## TDD 결과
- RED: 모듈이 없어 `ModuleNotFoundError`로 수집 단계에서 실패.
- GREEN: 신규 67개 통과. 전체 777개 통과(건너뜀 0), 커버리지 100%(920문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 실제 파일 확인: 저장소의 `.py`/`.tsx`는 통과, `.svg`·`.png`·`.exe`는 확장자로 거부, 실제 PNG를 `fake.py`로 이름만 바꾸면 `binary_file_rejected`로 거부.

## 제공 함수
| 함수 | 역할 |
|---|---|
| `get_extension(filename)` | 소문자 확장자(점 포함). 디렉터리(`/`, `\`) 무시, `.gitignore`·`trailing.`은 확장자 없음, `a.tar.gz`는 `.gz` |
| `validate_extension(filename)` | 지원 12개면 정규화된 확장자 반환, 아니면 `unsupported_file_type` |
| `validate_size(size_bytes)` | 10MB 초과 시 `file_too_large` (정확히 10MB는 허용, DB 제약과 동일) |
| `validate_total_size(sizes)` | 한 업로드의 파일 합계에 같은 한도 적용 |
| `is_binary(content)` / `validate_binary(content)` | 바이너리 판별 / 거부(`binary_file_rejected`) |
| `validate_file(filename, content)` | 위 검사를 확장자 → 크기 → 내용 순서로 실행, `ValidatedFile(extension, size_bytes)` 반환 |

## 기술 결정
- 확장자 목록과 10MB 한도는 모델 쪽 `SUPPORTED_EXTENSIONS`, `MAX_UPLOAD_SIZE_BYTES`를 그대로 가져온다. 검증기와 DB 제약이 어긋날 수 없다.
- 바이너리 판별은 파일 앞 8KB만 본다: (1) 알려진 파일 시그니처(PNG, JPEG, GIF, PDF, ZIP, gzip, ELF, Java class, SQLite, RAR, 7z), (2) NUL 바이트, (3) 허용 목록(탭, 개행, 폼피드, CR, ESC) 밖의 제어 문자 비율 5% 초과. 시그니처는 `MZ`처럼 소스 파일이 우연히 시작할 수 있는 짧은 것은 제외했다(`MZ = 5`로 시작하는 파이썬 파일이 통과함을 테스트로 고정).
- UTF-8 여부는 검사하지 않는다. CP949 같은 레거시 인코딩 소스를 바이너리로 오판하지 않기 위해서다. 디코딩 문제는 이후 단계의 몫이다.
- 오류는 `FileValidationError`(code, message, details, suggestion)로 통일했다. `utils`는 services/api에 의존하지 않는다. API 응답으로의 변환(HTTP 상태 매핑)은 업로드 서비스·라우터(T069 이후)에서 한다.
- 오류 형식은 요구사항 부록(FR-111)의 `file_too_large` 예시와 같다: `details.max_size_mb`, `details.uploaded_size_mb`, `suggestion`.

## 비고
- **명세 불일치**: spec.md FR-015는 확장자 9개(`.py .js .html .css .java .cpp .c .txt .md`)만 적었지만, data-model.md와 마이그레이션(T009)의 DB 제약은 `.ts .jsx .tsx`를 포함한 12개다. 구현은 DB 기준 12개를 따른다. spec.md를 고칠지 결정이 필요하다.
- UTF-16으로 저장된 소스는 NUL 바이트 때문에 바이너리로 거부된다(UTF-8 사용을 안내해야 함).
- 빈 파일(0바이트)은 통과한다. 명세에 거부 규칙이 없어 임의로 추가하지 않았다.
- FR-017(`.git`, `node_modules` 등 제외)과 FR-018(파일 1~20개)은 폴더 업로드를 다루는 T069(CodeUploadService)의 몫으로 남겨 두었다.
- 파일 하나가 아니라 합계 한도를 쓰려면 `validate_total_size`를 업로드 서비스가 호출해야 한다.
