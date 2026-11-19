# TASK-001. 프로젝트 디렉토리 구조 생성

## 상태
완료

## 날짜
2026-10-27

## 작업 요약
집을 짓기 전에 방과 창고의 위치를 정해 두는 것처럼, plan.md에 정의된 폴더 구조를 미리 만들었습니다.
백엔드(FastAPI)는 `models`, `api`, `db`, `utils`, `tasks`, `services/*` 폴더를, 프론트엔드(React)는 `components/*`, `pages`, `services`, `hooks`, `utils`, `stores`, `lib` 폴더를 갖추었고, 테스트용 폴더(`contract`, `integration`, `unit`)와 코드 파일 저장소 `storage/uploads/`, 문서 폴더 `docs/`도 만들었습니다.
빈 폴더는 Git이 추적하지 못하므로 각 빈 폴더에 `.gitkeep` 파일을 넣어 두었습니다.

## 변경 파일
- `backend/src/**`, `backend/tests/{contract,integration,unit}/`
- `frontend/src/**`, `frontend/tests/{integration,unit}/`
- `storage/uploads/`
- `docs/task-reports/`
- 각 빈 폴더의 `.gitkeep`
- `specs/001-ai-code-learning-platform/tasks.md` (T001 체크)

## TDD 결과
- RED 커밋: 해당 없음 (디렉토리 생성 작업으로 테스트 대상 코드 없음)
- GREEN 커밋: 해당 없음 (현재 디렉토리가 Git 저장소가 아님)
- 테스트 커버리지: 해당 없음
- 검증: 생성된 디렉토리 존재 여부를 `ls`로 확인

## 기술 결정
- 모든 경로에 슬래시(`/`)를 사용해 Git Bash/Windows 모두에서 동일하게 동작하도록 함.
- `frontend/src/stores`, `frontend/src/lib`는 plan.md 트리에는 없지만 tasks.md(T019, T021)에서 요구하므로 함께 생성.

## 비고
- 다음 작업: T002 (백엔드 Python 프로젝트 초기화).
- Git 저장소가 아니어서 커밋은 만들지 않았습니다.
