# TASK-090: LearningDocument SQLAlchemy 모델

## 상태
완료

## 날짜
2026-11-17

## 작업 요약
`learning_documents` 테이블에 대응하는 `LearningDocument` 모델을 만들었다. Task 하나당 하나씩 생기는 7챕터 학습 문서(JSONB)와 생성 진행 상태(대기/진행 중/완료/실패, 시작·종료 시각, 오류, Celery 작업 ID)를 담는다. 마이그레이션(T009)의 컬럼·제약·인덱스 이름을 그대로 따르고, `Task.learning_document` ↔ `LearningDocument.task` 일대일 관계를 연결했다.

## 변경 파일
- `backend/src/models/learning_document.py` (신규)
- `backend/src/models/__init__.py` (`LearningDocument` 내보내기)
- `backend/src/models/task.py` (`Task.learning_document` 관계 추가)
- `backend/tests/unit/test_learning_document_model.py` (신규, 메타데이터 검증)
- `backend/tests/integration/test_learning_document_model_db.py` (신규, 실제 DB 검증)

## TDD 결과
- RED: 모듈이 없어 두 테스트 파일 모두 수집 단계에서 실패.
- GREEN: 신규 48개 통과. 전체 1245개 통과(건너뜀 0), 커버리지 100%(1550문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 검증한 규칙: 상태 4가지(`pending`, `in_progress`, `completed`, `failed`)만 허용하고 `done`, `PENDING`, 빈 문자열, `queued`는 거부, 7개 챕터 키 중 하나라도 없으면 거부(키마다 하나씩 빼서 확인), content가 객체가 아니면(배열, 문자열, 숫자, JSON null) 거부, 챕터 값이 null이거나 여분의 키가 있어도 허용, Task당 문서 1개(중복 시 `learning_documents_task_id_key` 위반), `celery_task_id`는 255자까지, 한글과 중첩 구조가 JSONB에서 그대로 돌아옴, Task·프로젝트 삭제 시 DB가 문서를 연쇄 삭제, 모델이 실제 마이그레이션된 스키마와 일치(JSONB 타입 포함).

## 기술 결정
- **"빈 7챕터" 기본값(`empty_content()`)을 모델에 두었다.** `content`는 `NOT NULL`이고 `valid_content_structure` 제약이 7개 챕터 키가 모두 있는 객체를 요구한다. 그래서 아직 쓰이지 않은 `pending` 문서도, 생성에 실패한 문서도 7개 키가 있는 content를 가져야 한다. 기본값이 없으면 행을 만드는 순간 IntegrityError가 난다. 이후 문서 생성 서비스(T093~T094)가 이 행을 먼저 만들 것이므로, 호출하는 쪽마다 이 규칙을 기억하지 않도록 한 곳에 모았다. 문서의 상태는 content가 아니라 `generation_status`가 말한다. 호출마다 새 dict를 만들어 문서끼리 챕터 객체를 공유하지 않게 했다(테스트로 고정).
- **마이그레이션을 기준으로 삼았다.** data-model.md의 SQL은 `content ? 'chapter1' AND …`로 쓰였지만 마이그레이션의 실제 제약은 `content ?& ARRAY[…]`이다. 두 표현은 같은 의미이며 모델은 마이그레이션과 같은 이름(`valid_content_structure`)과 표현을 쓴다.
- 이름 없던 제약은 PostgreSQL이 붙인 이름(`learning_documents_task_id_key`, `learning_documents_generation_status_check`)을 `conv()`로 그대로 지정한다(Project, Task, UploadedCode 모델과 같은 방식).
- 상태 목록과 챕터 키는 `GENERATION_STATUSES`, `CHAPTER_KEYS` 상수로 노출했다. DB 제약 문자열도 이 상수에서 만들어 둘이 어긋나지 않는다. 이후 서비스가 같은 값을 쓸 수 있다.
- `__repr__`에는 ID와 상태만 넣는다. content(학습자 코드에 대한 설명)와 오류 메시지는 로그에 남기지 않는다.
- 관계는 `lazy="raise"`, `passive_deletes=True`, `uselist=False`로 다른 모델과 같은 규칙을 따른다.

## 비고
- JSONB 안쪽을 직접 고치는 것(`document.content["chapter1"]["title"] = …`)은 SQLAlchemy가 변경으로 감지하지 못한다. 변경은 새 dict를 대입해야 저장된다(모델 주석과 테스트에 명시). 챕터를 하나씩 채우는 서비스는 이 점을 지켜야 한다.
- 챕터 안쪽 구조(title, concepts 등)는 DB가 검사하지 않는다. 필수 필드 검증은 이후 단계(문서 생성 서비스)의 몫이다.
- `generation_status`는 DB에서 NULL을 허용한다(마이그레이션이 `NOT NULL`을 걸지 않았다). 모델도 같게 두었고, 서비스는 항상 값을 넣어야 한다.
- `ruff format --check`의 기존 지적(`tests/unit/test_token_service.py`)은 이번 작업과 무관하다.
