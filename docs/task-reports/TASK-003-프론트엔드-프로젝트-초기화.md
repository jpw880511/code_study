# TASK-003. 프론트엔드 React + Vite + TypeScript 프로젝트 초기화

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
새 가게를 열기 전에 기본 가구가 갖춰진 빈 매장을 마련한 것과 같습니다. Vite 공식 `react-ts` 템플릿으로 프론트엔드 뼈대를 만들어 `frontend/`에 넣고, 의존성을 설치한 뒤 빌드가 성공하는지 확인했습니다. 앞서 만든 `components/`, `pages/` 등 폴더는 그대로 유지했습니다.

## 변경 파일
- `frontend/package.json`, `index.html`, `vite.config.ts`
- `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
- `frontend/src/main.tsx`, `App.tsx`, `index.css`, `App.css`, `assets/`
- `frontend/public/`, `frontend/.gitignore`
- `specs/001-ai-code-learning-platform/tasks.md` (T003 체크)

## TDD 결과
- RED 커밋: 해당 없음 (프로젝트 스캐폴딩으로 직접 작성한 로직 없음)
- GREEN 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: 해당 없음
- 검증: `npm install` (취약점 0건), `npm run build` (tsc + vite build) 성공

## 기술 결정
- 템플릿이 기본 포함한 oxlint는 제거함. constitution은 ESLint + Prettier를 요구하며 T006에서 설정함.
- `tsconfig.app.json`에 `"strict": true`를 명시 (constitution의 TypeScript strict 요구).
- 템플릿 버전(React 19, Vite 8, TypeScript 7)을 그대로 사용. 계획의 "React 18+"를 만족.
- 비어 있지 않은 폴더에 `create-vite`를 직접 쓰면 기존 파일과 충돌하므로 임시 폴더에서 생성 후 덮어쓰지 않는 복사(`cp -n`)로 반영.
- `App.tsx`의 데모 코드는 T018(React Router 구성)에서 교체 예정.

## 비고
- 다음 작업: T004 (Docker Compose 구성).
