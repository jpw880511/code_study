# TASK-004. Docker Compose 구성 (PostgreSQL, Redis)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
개발에 필요한 두 가지 "공용 설비"인 데이터 창고(PostgreSQL 15)와 임시 메모판(Redis 7)을 명령 한 번으로 켜고 끌 수 있도록 `docker-compose.yml`을 작성했습니다. 각 설비에는 "정상 작동 중인지" 스스로 확인하는 건강 점검(healthcheck)을 붙였고, 데이터는 볼륨에 보관되어 컨테이너를 껐다 켜도 유지됩니다.

## 변경 파일
- `docker-compose.yml` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T004 체크)

## TDD 결과
- RED 커밋: 해당 없음 (인프라 설정 파일로 테스트 대상 코드 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: `docker compose up -d` 실행 결과 db(postgres:15-alpine), redis(redis:7-alpine) 모두 healthy 상태, `redis-cli ping` 응답 PONG 확인. YAML 구조도 파싱으로 확인.

## 기술 결정
- DB 이름/계정/비밀번호는 `${POSTGRES_USER:-postgres}` 형태로 환경변수를 읽고 기본값은 quickstart.md의 개발용 값을 사용. 실제 값은 T005의 `.env`로 덮어쓰며, 운영에서는 기본 비밀번호를 쓰면 안 됨.
- 서비스명은 quickstart.md의 `DATABASE_URL`(호스트 `db`), `REDIS_URL`(호스트 `redis`)과 일치시킴.
- 백엔드/프론트엔드는 컨테이너화하지 않음 (plan.md상 Dockerfile 없음, YAGNI). 호스트에서 직접 실행.
- 최신 Compose 사양에 맞춰 `version:` 키는 생략.

## 비고
- 다음 작업: T005 (.env.example 작성).
