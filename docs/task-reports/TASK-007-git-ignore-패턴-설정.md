# TASK-007. Git ignore 패턴 설정

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
우편물을 보낼 때 "이건 부치지 말 것" 목록을 만들어 두는 것과 같습니다. 프로젝트 루트에 `.gitignore`를 만들어 비밀 정보(`.env`), 가상환경(`.venv`), 설치된 라이브러리(`node_modules`), 빌드 결과물, 캐시, 사용자가 업로드한 코드 파일(`storage/uploads/`)이 Git에 올라가지 않게 했습니다. 단, `.env.example`과 업로드 폴더의 `.gitkeep`은 예외로 추적됩니다.

## 변경 파일
- `.gitignore` (신규)
- `specs/001-ai-code-learning-platform/tasks.md` (T007 체크)

## TDD 결과
- RED 커밋: 해당 없음 (설정 파일)
- GREEN 커밋: 해당 없음 (현재 디렉토리가 Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: 임시 Git 저장소에서 `git check-ignore`로 확인. 무시됨: `.env`, `.env.local`, `backend/.venv`, `__pycache__`, `node_modules`, `dist`, `storage/uploads/*`, `*.log`. 추적됨: `.env.example`, `storage/uploads/.gitkeep`, 일반 소스 파일.

## 기술 결정
- `storage/uploads/`는 디렉토리 자체가 아니라 내용(`/*`)만 무시해야 `.gitkeep` 예외가 동작하므로 `storage/uploads/*` + `!storage/uploads/.gitkeep` 사용.
- `.vscode/`는 팀 공유 설정(저장 시 포맷 등)을 쓸 수 있어 무시하지 않음. `.idea/`는 무시.
- Dockerfile이 없어 `.dockerignore`는 만들지 않음. `frontend/.gitignore`(Vite 템플릿)는 그대로 유지.

## 비고
- Phase 1(Setup) 완료. 다음 단계: Phase 2 T008 (Alembic 마이그레이션 프레임워크).
- 아직 Git 저장소가 아니므로, 커밋을 시작하려면 `git init`이 필요합니다.
