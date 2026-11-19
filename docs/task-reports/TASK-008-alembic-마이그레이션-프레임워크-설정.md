# TASK-008. Alembic 마이그레이션 프레임워크 설정

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
건물을 증축할 때 "몇 층을 언제 어떻게 올렸는지" 공사 일지를 남기는 것처럼, 데이터베이스 구조 변경 이력을 관리하는 Alembic을 `backend/alembic/`에 세팅했습니다. 접속 주소는 코드에 적지 않고 환경변수 `DATABASE_URL`(또는 루트 `.env`)에서 읽도록 `env.py`를 고쳤습니다. 실제 테이블 정의는 T009에서 손으로 작성한 SQL로 추가합니다.

## 변경 파일
- `backend/alembic.ini` (신규, 접속 URL 비움)
- `backend/alembic/env.py` (DATABASE_URL 읽기, `.env` 로드)
- `backend/alembic/script.py.mako`, `README`
- `backend/alembic/versions/.gitkeep`
- `specs/001-ai-code-learning-platform/tasks.md` (T008 체크)

## TDD 결과
- RED 커밋: 해당 없음 (프레임워크 설정, 직접 작성한 비즈니스 로직 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증 (docker의 실제 PostgreSQL 대상):
  - 임시 빈 리비전 생성 → `upgrade head` 성공 → `current`가 `000 (head)` → `downgrade base` 성공 → 임시 파일 삭제
  - `DATABASE_URL` 미설정 시 "DATABASE_URL is not set" 명확한 오류
  - `ruff`, `black --check` 통과

## 기술 결정
- 마이그레이션은 동기 드라이버(psycopg2)로 실행하므로 `DATABASE_URL`을 `postgresql://` 형식 그대로 사용. 비동기 앱 연결(asyncpg)은 T010/T011에서 URL 접두사를 변환할 예정.
- `target_metadata = None`: tasks.md T009가 autogenerate 없이 수동 SQL을 요구하므로 모델 연결 불필요.
- URL의 `%`는 configparser 보간 때문에 `%%`로 이스케이프.
- `.env`는 `backend/`의 두 단계 위(프로젝트 루트)에서 로드. 이미 설정된 환경변수가 우선.

## 비고
- 이 검증으로 로컬 DB에 빈 `alembic_version` 테이블이 남아 있습니다 (무해).
- 로컬 DB 비밀번호는 docker-compose 기본값(`postgres`)입니다. `.env`를 만들 때 맞춰야 합니다.
- 다음 작업: T009 (Base 모델 및 초기 스키마 마이그레이션).
