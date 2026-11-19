# TASK-005. 환경 설정 템플릿(.env.example) 생성

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
이사 갈 때 "여기에 전기 요금, 인터넷 비밀번호를 적으세요"라고 빈칸이 있는 안내 양식을 만드는 것과 같습니다. 실제 비밀번호와 API 키는 각자 `.env`에 적고, 저장소에는 빈칸 양식인 `.env.example`만 두도록 했습니다. 데이터베이스, Redis, Gemini API 키, JWT 비밀키, 환경/CORS, 파일 저장소, 프론트엔드(Vite) 설정 항목을 담았습니다.

## 변경 파일
- `.env.example` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T005 체크)

## TDD 결과
- RED 커밋: 해당 없음 (설정 템플릿으로 테스트 대상 코드 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: quickstart.md의 환경변수 목록과 대조하여 모든 항목 포함 확인

## 기술 결정
- quickstart.md는 호스트명을 `db`, `redis`(컨테이너 내부 주소)로 적었지만, 백엔드를 호스트에서 직접 실행하므로 `localhost`로 설정.
- 비밀번호/키는 `change-me`, `your-...-here` 같은 자리표시자만 사용 (constitution의 민감정보 하드코딩 금지). docker-compose.yml의 기본값(`postgres`)을 쓰려면 `.env`에서 맞춰야 함.
- `DATABASE_URL`은 plain `postgresql://`. 비동기 드라이버 접두사(`postgresql+asyncpg://`) 처리는 T010/T011에서 결정.
- `VITE_*` 변수는 Vite가 `frontend/.env`에서 읽으므로 주석으로 명시.

## 비고
- `.env`가 커밋되지 않도록 T007에서 Git ignore 패턴을 추가해야 합니다.
- 다음 작업: T006 (린트/포맷 설정).
