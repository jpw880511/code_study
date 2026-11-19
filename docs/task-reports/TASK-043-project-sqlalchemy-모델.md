# TASK-043. Project SQLAlchemy 모델 (소프트 삭제 필드 포함)

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
"프로젝트 서랍장"의 설계도입니다. 이미 만들어져 있는 `projects` 표(T009 마이그레이션)를 코드에서 다룰 수 있게 `Project` 모델을 추가했습니다. 모델은 구조만 정의하고 규칙(제목 길이 검사, 소유자 확인 등)은 서비스가 맡습니다.
- 열: `id`, `user_id`(users 삭제 시 함께 삭제), `title`(255자, 필수), `description`(TEXT), `created_at`/`updated_at`, `last_activity_at`, `deletion_status`(기본 `active`), `trashed_at`, `scheduled_deletion_at`
- 제약/인덱스: 마이그레이션과 **이름까지 동일**(`title_min_length`, `projects_deletion_status_check`, `idx_projects_user_id`, `idx_projects_deletion_status`, 부분 인덱스 `idx_projects_user_active ... WHERE deletion_status = 'active'`)
- 관계: `User.projects` / `Project.user` (`lazy="raise"`, `cascade="all, delete-orphan"`, `passive_deletes=True`) — `refresh_tokens`와 같은 방식
- `__repr__`은 id만 보여 주고 제목/설명 같은 내용은 노출하지 않음

## 변경 파일
- `backend/src/models/project.py` (신규), `backend/src/models/__init__.py` (`Project` 내보내기), `backend/src/models/user.py` (`projects` 관계 추가)
- `backend/tests/unit/test_project_model.py` (신규, 14개), `backend/tests/integration/test_project_model_db.py` (신규, 15개)

## TDD 결과
- RED: 테스트 먼저 작성 → `cannot import name 'Project' from 'src.models'`로 수집 단계 실패 확인
- GREEN: 모델 구현 후 모델 테스트 29개 전부 통과
- REFACTOR: Ruff/Black/MyPy(strict) 통과
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/models/project.py` 100%
- 검증 범위: 열 이름/널 허용/길이/기본값, FK `ON DELETE CASCADE`, 제약 이름 2개, 인덱스 3개(부분 인덱스 조건 포함)가 **마이그레이션된 실제 스키마와 일치**하는지 비교, DB가 채우는 기본값(비동기에서 reload 없이 접근 가능), 제목 빈 값/256자/누락, 잘못된 `deletion_status`, 없는 사용자, 사용자 삭제 시 프로젝트 삭제, 관계 명시 로딩

## 기술 결정
- **이름 없는 CHECK 제약도 이름을 맞춤.** 마이그레이션의 `deletion_status` 체크는 이름을 주지 않아 PostgreSQL이 `projects_deletion_status_check`로 자동 이름을 붙였습니다. 모델에서도 `conv()`로 같은 이름을 줘서 스키마 비교 테스트가 통과하고, 나중에 autogenerate가 불필요한 변경을 만들지 않게 함.
- `last_activity_at`, `deletion_status`는 DB에서 NULL 허용이므로 모델도 `| None`으로 동일하게 둠(마이그레이션이 진실의 원천).

## 비고
- 새 마이그레이션은 만들지 않았습니다(표는 T009에 이미 있음).
- 다음 작업: T044 (ProjectService).
