# TASK-006. 린트 및 포맷 설정 (Ruff/Black/MyPy, ESLint/Prettier)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
글을 쓸 때 맞춤법 검사기와 서식 정리 도구를 미리 켜 두는 것과 같습니다. 백엔드는 `pyproject.toml`에 Ruff(규칙 검사), Black(서식), MyPy(strict 타입 검사), pytest·coverage 설정을 모았고, 프론트엔드는 `eslint.config.js`(ESLint + typescript-eslint + React Hooks)와 `.prettierrc`, `.prettierignore`를 만들고 `lint`, `format`, `format:check` 스크립트를 추가했습니다.

## 변경 파일
- `backend/pyproject.toml` (신규)
- `frontend/eslint.config.js`, `.prettierrc`, `.prettierignore` (신규)
- `frontend/package.json` (devDependencies, scripts), `package-lock.json`
- `frontend/src/**` (Prettier 포맷 적용)
- `specs/001-ai-code-learning-platform/tasks.md` (T006 체크)

## TDD 결과
- RED 커밋: 해당 없음 (도구 설정으로 테스트 대상 코드 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: `npm run lint`, `npm run format:check`, `npm run build` 통과. 백엔드는 임시 파일(삭제함)로 `ruff check`, `black --check`, `mypy` 통과 확인. `src/`에 아직 .py 파일이 없어 실제 코드 검사는 이후 Task부터 적용.

## 기술 결정
- **TypeScript를 7.0 → 5.9로 변경**: typescript-eslint(8.72.1)의 peer 의존성이 TypeScript `<6.1.0`이라 TS 7과 설치가 충돌. `--force` 대신 호환되는 5.9.3으로 내림(T003에서 설치한 버전 변경). `tsconfig`는 수정 없이 빌드 통과. typescript-eslint가 TS 7을 지원하면 재검토.
- 줄 길이는 Python/TS 모두 100으로 통일.
- Ruff 규칙: E, F, I(import 정렬), UP, B. Black과 충돌하는 규칙은 선택하지 않음.
- `alembic/versions`는 수동 SQL 마이그레이션이라 린트 대상에서 제외.
- MyPy는 constitution에 따라 `strict = true`.
- Prettier: 세미콜론 없음, 작은따옴표, trailing comma all.

## 비고
- 다음 작업: T007 (.gitignore 패턴).
