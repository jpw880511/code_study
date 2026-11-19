# TASK-099. T099 Monaco Editor 설치·설정 (얇은 래퍼 `CodeEditor`)

## 상태
완료 (jsdom 테스트 + 실제 브라우저(Chromium) 일회성 확인. 실제 서버와의 연동은 미확인)

## 날짜
2026-11-18

## 작업 요약
Monaco를 `CodeEditor` 래퍼 하나에 가두고, 나머지 코드는 Monaco를 직접 알지 못하게 했습니다.

- `CodeEditor.tsx`: `React.lazy(() => import('./MonacoEditor'))`로 편집기를 별도 청크로 늦게 불러옵니다(코드 패널이 처음 그려질 때). 불러오는 동안 "코드 편집기를 불러오는 중..."(`role="status"`), 청크 로딩 실패(오프라인·오래된 배포)는 에러 경계로 "코드 편집기를 불러오지 못했습니다..."(`role="alert"`)를 보여 줘 페이지 전체가 죽지 않게 했습니다. 공개 props: `code`, `language`, `label`, `highlight`(`{start, end, nonce}` 또는 null), `onTopLineChange`.
- `MonacoEditor.tsx`: 실제 편집기. 읽기 전용, 줄 번호, 미니맵 없음, 줄 범위 강조(`code-highlight-line` 장식, 줄 전체), 강조 시 그 줄로 스크롤(`revealLineNearTop`, 즉시), 보이는 첫 줄 변경 알림. 코드/언어가 바뀌면 내용·언어를 교체하고 맨 위로 돌아갑니다.
- `monaco-runtime.ts`: Monaco를 불러오는 유일한 모듈. `monaco-editor/editor/editor.api`(편집기 코어) + `languages/definitions/register.all`(기본 구문 강조 토크나이저, 언어별 청크로 필요할 때만 로드) + `editor.worker?worker`(Vite `?worker`로 번들에 포함). `self.MonacoEnvironment.getWorker`를 설정했습니다. 서버가 주는 언어 이름(`c++`, `js`, `py` 등)을 Monaco 언어 id로 바꾸고 모르는 언어는 `plaintext`로 보여 줍니다.
- `src/monaco-modules.d.ts`: 경로로 가져오는 Monaco 모듈의 타입 선언.
- `index.css`에 강조 줄 배경 스타일 추가.

## 변경 파일
- `frontend/package.json`, `frontend/package-lock.json` (`monaco-editor` 0.57.0 정확히 고정)
- `frontend/src/components/document/CodeEditor.tsx` (생성)
- `frontend/src/components/document/MonacoEditor.tsx` (생성)
- `frontend/src/components/document/monaco-runtime.ts` (생성)
- `frontend/src/monaco-modules.d.ts` (생성)
- `frontend/src/index.css` (수정)
- `frontend/vite.config.ts` (커버리지 제외 목록에 `monaco-runtime.ts` 추가)
- `frontend/tests/unit/MonacoEditor.test.tsx`, `CodeEditor.test.tsx`, `CodeEditor-load-failure.test.tsx` (생성)
- `frontend/tests/helpers/fake-code-editor.tsx` (생성, 다른 컴포넌트 테스트가 쓰는 가짜 편집기)

## TDD 결과
- RED: `CodeEditor`/`MonacoEditor` 모듈이 없어 3개 파일이 실패하는 것을 확인했습니다. 이후 "사용자 입력이 있어야 스크롤 알림" 규칙(아래)은 테스트를 먼저 바꿔 3개 실패를 확인한 뒤 구현했습니다.
- GREEN: `MonacoEditor` 17개, `CodeEditor` 2개 통과(가짜 Monaco API로 `create` 옵션, 내용/언어 교체, 강조/해제, 새 nonce 재스크롤, 사용자 입력 판정, 리스너 정리, 해제 시 `dispose` 검증).
- 전체: 506개 통과(작업 전 400개).
- 실제 브라우저 확인(일회성, 임시 하네스를 만들어 빌드해 Chromium으로 확인한 뒤 삭제): 편집기 렌더, 줄 번호, python/javascript 구문 강조 토큰, 3줄 강조, 강조 줄로 스크롤, 마우스 휠 스크롤이 첫 줄로 보고됨, 파일 전환, 외부 도메인 요청 0건, 콘솔 오류 0건.
- 커버리지: 전체 문장 99.87%, 분기 97.83%. `monaco-runtime.ts`는 jsdom에서 실행할 수 없어 커버리지에서 제외했습니다(테스트는 이 모듈을 가짜로 대체).

## 기술 결정
- 설치 패키지: `monaco-editor` 0.57.0 하나만. 이유: 요구사항(번들 포함, CDN 없음)을 충족하는 공식 패키지. `@monaco-editor/react`는 기본이 CDN 로더라 쓰지 않았습니다.
- 버전 고정(`--save-exact`): 0.57의 경로 구조(`monaco-editor/editor/editor.api`, `languages/definitions/...`)에 의존하므로 자동 업그레이드를 막았습니다.
- 번들 크기(전/후): 메인 `index-*.js` 480.85 kB(gzip 154.59) -> 495.68 kB(gzip 158.46), +14.8 kB. 이 증가는 문서 화면 컴포넌트(뷰어, 챕터 7개, 훅 등)이고 Monaco가 아닙니다. Monaco는 별도 청크: `MonacoEditor-*.js` 2,718 kB(gzip 698), 워커 `editor.worker-*.js` 304 kB, CSS 99 kB, 언어별 토크나이저 청크 약 80개. 모두 문서가 완료되어 코드 패널이 처음 그려질 때 내려받습니다. 빌드의 "500 kB 초과 청크" 경고는 이 Monaco 청크 때문이며 의도한 분리입니다.
- 스크롤 알림은 **사용자 입력(휠, 터치, 키, 스크롤바 드래그)이 직전 500 ms 안에 있었을 때만** 보고합니다. 처음에는 "프로그램이 스크롤하는 동안 플래그"를 썼지만, 실제 브라우저에서 파일을 바꾼 뒤 비동기 레이아웃 스크롤 이벤트가 플래그 밖에서 도착해 엉뚱한 줄이 보고되는 것을 확인해 입력 기반으로 바꿨습니다. 이 방식은 `DocumentViewer`의 재진입 방지의 기반입니다.
- 에디터는 `highlight` 객체가 바뀔 때마다(새 `nonce`) 다시 강조하고 스크롤합니다. 부모는 객체를 상태로 유지해야 합니다.

## 비고
- `npm audit`: 의존성 `dompurify`(Monaco가 번들로 의존)에 알려진 취약점이 보고됩니다. 0.56.0도 마찬가지(경고 순환)여서 최신 0.57.0을 썼습니다. 이 앱은 Monaco의 마크다운/호버 렌더링에 외부 입력을 넣지 않고(읽기 전용, 코드는 텍스트로만 전달), 문서 내용은 HTML로 렌더링하지 않으므로 직접 영향은 없다고 판단하지만, Monaco 새 릴리스가 나오면 올리는 것을 권합니다.
- 구문 강조는 Monaco 기본 토크나이저(Monarch)만 있습니다. TypeScript/JSON/CSS/HTML의 언어 서비스(자동 완성, 오류 표시)는 번들에 넣지 않았습니다(읽기 전용 뷰어라 불필요, 워커 하나로 충분).
- 접근성: 편집기 `ariaLabel`은 "{파일명} 코드"입니다. 스크린 리더로 읽기 전용 Monaco를 쓰는 경험은 실제 확인하지 않았습니다.
