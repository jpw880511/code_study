# TASK-022. Tailwind CSS 설정과 shadcn/ui 컴포넌트 설치

## 상태
완료

## 날짜
2026-11-04

## 작업 요약
집을 지은 뒤 "페인트와 기본 가구 세트"를 들여놓은 작업입니다. 화면을 꾸미는 도구(Tailwind CSS)를 연결하고, 버튼, 입력창 같은 기성 부품(shadcn/ui)을 프로젝트에 설치했습니다.
- Tailwind CSS 4를 Vite 플러그인으로 연결 (`vite.config.ts`, `src/index.css`).
- `@/` 경로 별칭(`@/components/...`)을 Vite, TypeScript(`tsconfig.json`, `tsconfig.app.json`)에 설정.
- `shadcn init`으로 `components.json`(스타일 `radix-nova`, 아이콘 Lucide, 폰트 Geist), 색상 변수 기반 테마(`src/index.css`), `cn` 유틸(`src/lib/utils.ts`) 생성.
- 컴포넌트 7개 설치(`src/components/ui/`): Button, Input, Label, Textarea, Card, Tabs, Dialog. 곧 만들 로그인/회원가입 폼(T032, T033), Task 상세의 탭(T083), 삭제 확인 창(T185)에서 쓰는 것들입니다.

## 변경 파일
- `frontend/vite.config.ts` (Tailwind 플러그인, `@` 별칭), `frontend/tsconfig.json`, `frontend/tsconfig.app.json` (`paths`)
- `frontend/src/index.css` (Vite 템플릿의 기본 스타일을 Tailwind와 shadcn 테마로 교체)
- `frontend/components.json`, `frontend/src/lib/utils.ts`, `frontend/src/components/ui/*.tsx` 7개 (신규, CLI가 생성)
- `frontend/eslint.config.js` (shadcn 폴더에만 `react-refresh/only-export-components` 규칙 해제)
- `frontend/tests/unit/ui-components.test.tsx` (신규)
- `frontend/package.json`, `package-lock.json`
- `specs/001-ai-code-learning-platform/tasks.md` (T022 체크)

## TDD 결과
- RED: 컴포넌트 테스트를 먼저 작성 → 아직 없는 `card` 등을 불러오지 못해 실패 확인
- GREEN: `shadcn add`로 컴포넌트 설치 후 19개 통과. 전체 130개 통과
- REFACTOR: Prettier 정리, ESLint 오류 3건 처리(아래), 타입 검사 포함 빌드 통과 후 재실행 130개 유지
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 문장 99.1%, 분기 96.6% (CLI가 생성한 컴포넌트의 일부 분기는 미실행)
- 검증 범위: `cn`의 Tailwind 클래스 충돌 해소, Button(클릭, 비활성, 변형과 크기, 클래스 덮어쓰기, 링크로 렌더링), Input/Label/Textarea(입력, 연결, 비활성), Card 구성, Tabs(기본 탭, 클릭 전환, 방향키 이동), Dialog(열기, 취소/Escape로 닫기, 접근성 이름과 설명, 확인 동작)
- 실제 브라우저(Chrome) 검증: 임시 확인 페이지를 만들어 버튼 6가지 변형, 카드, 입력창, 탭 전환, 대화상자(배경 흐림 포함)가 스타일과 함께 정상 표시됨을 확인한 뒤 임시 파일 삭제

## 기술 결정
- **스타일 프리셋은 기본값인 Nova(Lucide/Geist)를 선택.** CLI가 대화형 선택을 요구해 기본 항목으로 지정했습니다. 외형(색, 모서리 반경, 글꼴)은 `src/index.css`의 변수로 바꿀 수 있습니다.
- **`shadcn`, `tailwindcss`, `@tailwindcss/vite`, `tw-animate-css`를 devDependencies로 이동.** `shadcn init`이 CLI 패키지를 `dependencies`에 넣었는데, 앱은 그 안의 CSS 파일 하나만 쓰고 나머지는 코드 생성 도구(ts-morph, deepmerge, minimatch 포함)입니다. 그대로 두면 운영 의존성 점검(`npm audit --omit=dev`)에 6건(낮음 2, 중간 4)이 나타났고, 이동 후 0건으로 돌아왔습니다. 운영 번들 크기는 변함없음.
- **`cn` 유틸이 `clsx`+`tailwind-merge` 대신 npm 패키지 `cn`(0.5.2)을 사용.** 이번 버전의 CLI가 생성한 방식입니다. 설치 전에 확인한 내용: 관리자는 shadcn 본인, 저장소는 `github.com/shadcn-ui/cn`, MIT, 설치 스크립트와 의존성 없음. 다만 1.0 이전 버전이고 이틀 전(2026-11-02)에 갱신된 새 패키지입니다. 불안하면 `src/lib/utils.ts`를 `clsx`+`tailwind-merge` 구현으로 바꾸면 됩니다(테스트가 동작을 고정하고 있음).
- **ESLint:** shadcn 파일은 컴포넌트와 `buttonVariants` 같은 보조 함수를 한 파일에서 내보내는데, 이는 핫 리로드에만 영향을 주는 규칙(`react-refresh/only-export-components`)에 걸립니다. 생성된 파일을 고치지 않고 `src/components/ui/`에만 이 규칙을 해제했습니다.
- 토스트(T204)와 그 밖의 컴포넌트는 필요한 Task에서 `npx shadcn@latest add`로 추가합니다. 지금 미리 설치하지 않음.

## 비고
- **개발 서버 재시작이 필요합니다.** `vite.config.ts`를 바꾼 뒤에는 이미 실행 중이던 개발 서버가 `@` 별칭을 인식하지 못해 새 화면이 비어 보였습니다(코드 문제가 아님). 서버를 다시 시작해서 해결했고, 설정 변경 후에는 서버를 다시 시작해야 합니다.
- **기본 화면 스타일이 바뀌었습니다.** Vite 템플릿의 전역 스타일(가운데 정렬, 보라색 강조 등)을 Tailwind의 기본 초기화 스타일로 교체했습니다. 현재 페이지들은 내용만 있는 자리표시 화면이라 평범하게 보이며, 실제 페이지 Task에서 스타일을 입힙니다.
- 이 Task로 Phase 2의 프론트엔드 기반(T018~T022)이 모두 끝났습니다. 다음은 인증 슬라이스(Phase 3, T023~)입니다.
