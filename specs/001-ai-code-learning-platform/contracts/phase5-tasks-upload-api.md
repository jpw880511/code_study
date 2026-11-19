# Phase 5 계약: Task 와 코드 업로드 API (T067–T083)

백엔드(T067–T075)와 프론트엔드(T076–T083)가 **동시에** 개발하므로, 이 문서가 둘 사이의 유일한 약속이다.
서로의 코드를 기다리지 말고 이 문서만 보고 구현한다. 문서와 다르게 만들어야 할 이유를 발견하면 구현을 바꾸지 말고 보고한다.

- 모든 경로는 `/api/v1` 아래. 인증은 기존 HttpOnly 쿠키(`access_token`). 로그인 없으면 `401 not_authenticated`.
- 오류 본문은 기존 형식: `{"error": "<code>", "message": "<한국어>", "details"?: {...}, "suggestion"?: "<한국어>"}`.
- 시각은 ISO 8601 문자열, id는 UUID 문자열.
- 목록은 **bare array**, 삭제는 **204 빈 본문**, 부분 수정은 보낸 필드만 변경(기존 프로젝트 API와 동일).
- 응답에 `storage_path`, `user_id`, 삭제 관련 컬럼(`deletion_status`, `trashed_at`, `scheduled_deletion_at`)을 절대 넣지 않는다.

## 1. 응답 형태

### TaskResponse
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "task_number": 1,
  "title": "계산기 함수 학습",
  "description": "설명 또는 null",
  "upload_method": "file | folder | paste | null",
  "created_at": "2026-11-16T09:00:00Z",
  "updated_at": "2026-11-16T09:00:00Z",
  "upload": null
}
```
`upload`는 업로드된 코드가 있으면 다음 객체, 없으면 `null`:
```json
{
  "detected_language": "python | null",
  "complexity_level": "beginner | intermediate | advanced | null",
  "total_lines": 120,
  "total_files": 3,
  "upload_size_bytes": 4096
}
```

### CodeFileSummary
```json
{
  "id": "uuid",
  "file_name": "App.jsx",
  "file_path": "src/App.jsx 또는 null",
  "file_extension": ".jsx | null",
  "file_size_bytes": 2048,
  "mime_type": "text/javascript | null"
}
```

### TaskDetailResponse = TaskResponse + `files`
`files`: `CodeFileSummary[]`, `file_path`(없으면 `file_name`) 오름차순.

### CreateTaskResponse = TaskDetailResponse + 업로드 결과
```json
{
  "...TaskDetailResponse": "...",
  "excluded_paths": [".git/config", "node_modules/a/index.js"],
  "warnings": [{"code": "large_code", "message": "..."}]
}
```
- `excluded_paths`: 폴더 업로드에서 서버가 자동 제외한 경로(FR-017). 없으면 `[]`.
- `warnings`: 코드 줄 수(복잡도 분석의 `code_lines`)가 500줄을 넘으면 `large_code` 하나:
  "큰 코드 파일이 감지되었습니다. 500줄을 넘는 코드는 문서 생성에 3~5분이 걸릴 수 있습니다. 다른 화면으로 이동했다가 준비되면 다시 돌아와도 됩니다." 없으면 `[]`.

### CodeResponse (`GET /tasks/{id}/code`)
```json
{
  "files": [
    {"id": "uuid", "file_name": "main.py", "file_path": null, "file_extension": ".py",
     "file_size_bytes": 120, "mime_type": "text/x-python", "language": "python", "content": "print(1)\n"}
  ]
}
```
`CodeFileSummary` 필드 + `language`(파일별 감지 언어, 모르면 `"unknown"`) + `content`(UTF-8, 잘못된 바이트는 대체 문자).
정렬은 `file_path`(없으면 `file_name`) 오름차순.

## 2. 엔드포인트

| 메서드 경로 | 요청 | 성공 | 비고 |
|---|---|---|---|
| `GET /projects/{project_id}/tasks` | – | 200 `TaskResponse[]` | `task_number` **오름차순**(FR-003). 휴지통 Task 제외 |
| `POST /projects/{project_id}/tasks` | multipart/form-data(아래) | **201** `CreateTaskResponse` | Task + 업로드를 한 번에 만든다 |
| `GET /tasks/{task_id}` | – | 200 `TaskDetailResponse` | |
| `PATCH /tasks/{task_id}` | JSON `{title?, description?}` | 200 `TaskResponse` | 하나 이상 필수. `description: null` 이면 지움. 번호·업로드는 바꿀 수 없다 |
| `DELETE /tasks/{task_id}` | – | **204** | 소프트 삭제(휴지통, 30일 후 영구삭제 예약) |
| `GET /tasks/{task_id}/code` | – | 200 `CodeResponse` | 저장된 파일 내용 |

### POST multipart 필드
| 필드 | 필수 | 설명 |
|---|---|---|
| `title` | 예 | 앞뒤 공백 제거 후 5자 이상 255자 이하 (FR-008) |
| `description` | 아니오 | 500자 이하 (FR-009), 공백만이면 null |
| `upload_method` | 예 | `file` / `folder` / `paste` |
| `files` | file·folder | 반복 파트(파일 1~20개) |
| `paths` | folder | `files`와 **같은 개수·같은 순서**의 텍스트 필드(반복). 각 값은 파일명을 포함한 `/` 구분 상대 경로, 예: `my-app/src/App.jsx` |
| `code` | paste | 붙여넣은 코드 텍스트 |
| `language` | paste | 드롭다운 값: `python`, `javascript`, `typescript`, `java`, `c`, `cpp`, `html`, `css`, `markdown`, `text` |

- `file` 방식에서 `paths`는 무시한다. `folder`에서 `paths` 개수가 `files`와 다르면 `422 invalid_file_path`.
- paste는 서버가 파일 하나를 만든다: 이름 `pasted_code<확장자>`, 확장자는 언어에서 정한다
  (python `.py`, javascript `.js`, typescript `.ts`, java `.java`, c `.c`, cpp `.cpp`, html `.html`, css `.css`, markdown `.md`, text `.txt`).
- **폴더 제외(FR-017)**: 경로의 어느 디렉터리 이름이 `.git`, `node_modules`, `__pycache__` 이거나 파일 이름이 `.DS_Store` 이면 제외하고 `excluded_paths`에 담는다. 제외한 뒤 남은 파일로 아래 검사를 한다. 제외 후 0개면 `422 no_files`.
- **검사 순서**: 방식·제목·설명 → 경로 정규화 → 제외 → 개수(1~20) → 파일별 `validate_file`(확장자→크기→바이너리) → 합계 `validate_total_size`(10MB). 하나라도 실패하면 **Task도 파일도 아무것도 만들지 않는다**(DB·디스크 모두 원상태).
- 파일은 최대 `MAX_UPLOAD_SIZE_BYTES + 1`바이트까지만 읽어 크기를 판정한다(거대한 파일로 메모리를 채우지 않도록).
- **경로 안전**: 절대 경로, `..` 세그먼트, 빈 세그먼트, 역슬래시 등은 `422 invalid_file_path`. 사용자가 보낸 이름·경로는 DB의 `file_name`/`file_path`에만 들어가고, 디스크 경로에는 **절대** 쓰지 않는다(서버가 만든 UUID + 검증된 확장자만 사용).

## 3. 오류 코드

| HTTP | error | message |
|---|---|---|
| 404 | `project_not_found` | (기존) 요청한 프로젝트를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 프로젝트입니다. |
| 403 | `project_forbidden` | (기존) 이 프로젝트에 접근할 권한이 없습니다. |
| 404 | `task_not_found` | 요청한 Task를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 Task입니다. |
| 403 | `task_forbidden` | 이 Task에 접근할 권한이 없습니다. |
| 404 | `code_not_found` | 이 Task에는 업로드된 코드가 없습니다. |
| 404 | `code_file_missing` | 저장된 코드 파일을 찾을 수 없습니다. |
| 422 | `invalid_task_title` | 최소: Task 제목은 최소 5자 이상이어야 합니다. / 최대: Task 제목은 최대 255자까지 입력 가능합니다. / NUL 문자: Task 제목에 사용할 수 없는 문자가 포함되어 있습니다. |
| 422 | `invalid_task_description` | Task 설명은 최대 500자까지 입력 가능합니다. (NUL 문자는 `Task 설명에 사용할 수 없는 문자가 포함되어 있습니다.`) |
| 422 | `invalid_upload_method` | 업로드 방식이 올바르지 않습니다. file, folder, paste 중 하나를 선택하세요. |
| 422 | `no_files` | 업로드할 파일을 선택하세요. |
| 422 | `too_many_files` | 업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요. |
| 422 | `invalid_file_path` | 파일 경로가 올바르지 않습니다. |
| 422 | `language_required` | 업로드하기 전에 프로그래밍 언어를 선택하세요. |
| 422 | `unsupported_language` | 지원하지 않는 프로그래밍 언어입니다. |
| 422 | `empty_code` | 붙여넣은 코드가 비어 있습니다. |
| 413 | `file_too_large` | (기존 `file_validator`) 파일 크기가 10MB를 초과합니다. / 업로드한 파일의 전체 크기가 10MB를 초과합니다. + `details.max_size_mb`, `details.uploaded_size_mb`, `suggestion` |
| 415 | `unsupported_file_type` | (기존) 지원하지 않는 파일 형식입니다 (.exe). + `details.extension`, `details.supported_extensions`, `suggestion` |
| 415 | `binary_file_rejected` | (기존) 바이너리 파일은 업로드할 수 없습니다. + `suggestion` |
| 422 | `validation_error` | (기존) 형식 자체가 틀린 요청(잘못된 UUID, PATCH 빈 본문 등) |

- 403/404 규칙은 프로젝트와 같다: 휴지통에 있는 Task, 휴지통에 있는 프로젝트의 Task는 **누구에게나 404**. 남의 것은 403.
- `file_too_large`/`unsupported_file_type`/`binary_file_rejected`는 `src/utils/file_validator.py`의 `FileValidationError`(코드·메시지·details·suggestion)를 그대로 응답으로 옮긴다.

## 4. 규칙 (백엔드 동작)

1. **task_number**: 프로젝트별 1부터 순차. `MAX(task_number)+1`을 **휴지통 Task까지 포함해서** 계산한다(번호 불변·재사용 금지, FR-004). 동시에 두 요청이 와도 같은 번호가 나가지 않도록 프로젝트 행을 `SELECT … FOR UPDATE`로 잠근 뒤 계산한다.
2. **저장 위치**: `{저장 루트}/{user_id}/{task_id}/{uuid4}{확장자}`. DB `code_files.storage_path`에는 **저장 루트 기준 상대 경로**(`/` 구분)를 넣는다. 저장 루트는 설정값(`UPLOAD_STORAGE_PATH`, 기본 저장소 루트의 `storage/uploads`)이고 테스트는 임시 폴더를 쓴다. 읽을 때 해석한 경로가 저장 루트 밖이면 거부한다.
3. **업로드 분석**: `UploadedCode`를 만든다 — `detected_language`: 코드 파일(markdown/text/unknown 제외) 중 줄 수가 가장 많은 언어, 코드 파일이 없으면 전체 중 가장 많은 언어, 동률은 먼저 올라온 쪽, 전부 unknown 이면 `"unknown"`. `complexity_level`: `assess()` 결과. `total_lines`: `assess().total_lines`. `total_files`, `upload_size_bytes`: 합계. 파일별 언어는 `detect_language(경로, 내용)`, 붙여넣기는 `normalize_language(language)`.
4. **프로젝트 연동**: Task 생성·수정·삭제 때 `projects.last_activity_at`을 갱신한다. **프로젝트를 소프트 삭제하면 그 프로젝트의 활성 Task도 같은 시각으로 휴지통에 보낸다**(FR-009D, `project_service.py`의 TODO).
5. **소프트 삭제**: `deletion_status='trashed'`, `trashed_at=now`, `scheduled_deletion_at=trashed_at+30일`. 파일은 디스크에 남긴다(복원·30일 보관 때문, 영구 삭제는 Phase 10).
6. **원자성**: 검사 실패나 DB 오류가 나면 디스크에 쓴 파일을 지운다. Task 폴더가 남으면 안 된다.
7. 서비스는 HTTP를 모른다(`DomainError` 서브클래스만 던진다). 상태 코드 매핑은 `api/exceptions.py`.

## 5. 프론트엔드 약속

- 파일 타입: `src/services/task-service.ts`에 위 응답 타입을 그대로 선언한다(`Task`, `TaskUpload`, `CodeFileSummary`, `TaskDetail`, `CreateTaskResult`, `TaskCode`).
- 함수: `listTasks(projectId)`, `createTask(projectId, input)`(multipart `FormData`; `Content-Type`은 axios가 경계값과 함께 정하게 두고 직접 지정하지 않는다), `getTask(id)`, `updateTask(id, input)`, `deleteTask(id)`, `getTaskCode(id)`.
- 폴더 업로드는 각 파일에 `file.webkitRelativePath`를 `paths`로 보낸다. 서버 제외를 믿지 말고 **브라우저에서 먼저** `.git`, `node_modules`, `__pycache__`, `.DS_Store`를 걸러 요청 크기를 줄이고, 걸러진 경로를 화면에 안내한다: "일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__".
- 업로드 전에 브라우저에서도 같은 규칙을 먼저 검사해 즉시 알려 준다(서버가 최종 판단): 확장자 12개(`.py .js .ts .jsx .tsx .html .css .java .cpp .c .txt .md`), 합계 10MB, 1~20개, 제목 5자 이상, 설명 500자 이하, paste는 언어 선택 필수.
- 오류 표시는 기존 `errorMessage(error, 대체문구)`를 쓰고, 서버의 `suggestion`이 있으면 함께 보여 준다.
- 화면 번호 표기: `Task {task_number}`. 목록은 서버가 준 순서(번호 오름차순)를 그대로 쓴다.
- 라우트: `/tasks/:taskId`(보호된 라우트). Task 수정/삭제 UI는 이번 범위가 아니다.
