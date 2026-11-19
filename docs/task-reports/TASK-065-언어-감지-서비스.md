# TASK-065: 언어 감지 서비스 (Pygments)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
업로드된 파일의 프로그래밍 언어를 이름 붙이는 서비스를 만들었다(FR-020). 파일 이름을 Pygments로 해석하고, 확장자가 없는 스크립트는 첫 줄 셔뱅(`#!`)으로 판별한다. 붙여넣기 업로드에서 사용자가 드롭다운(FR-013)으로 고른 언어를 같은 이름 체계로 바꾸는 `normalize_language()`도 제공한다.

## 변경 파일
- `backend/src/services/code_analysis/language_detector.py` (신규)
- `backend/src/services/code_analysis/__init__.py` (신규, 빈 파일 — 이 패키지에 `__init__.py`가 없었다)
- `backend/tests/unit/test_language_detector.py` (신규, 82개)
- `backend/requirements.txt` (`pygments>=2.17` 선언 추가)
- `backend/pyproject.toml` (Pygments에 대한 mypy `ignore_missing_imports`)

## 제공 함수
| 함수 | 역할 |
|---|---|
| `detect_language(filename, content="")` | 언어 이름 또는 `"unknown"`. `.txt`는 셔뱅이 없으면 `"text"` |
| `normalize_language(name)` | 사용자가 고른/입력한 이름을 정규 이름으로(`"c++"`→`cpp`, `"JS"`→`javascript`), 모르면 `None` |
| `UNKNOWN_LANGUAGE`, `TEXT_LANGUAGE` | 상수 |

지원 확장자 12개의 결과: `.py` python, `.js`/`.jsx` javascript, `.ts`/`.tsx` typescript, `.html` html, `.css` css, `.java` java, `.cpp` cpp, `.c` c, `.md` markdown, `.txt` text.

## TDD 결과
- RED: 모듈이 없어 `ModuleNotFoundError`로 수집 단계에서 실패.
- GREEN: 신규 82개 통과. 전체 859개 통과(건너뜀 0), 커버리지 100%(970문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 첫 전체 실행에서는 Docker가 꺼져 DB 테스트가 건너뛰어졌다(커버리지 85%). 그 수치는 무시하고 Docker/Postgres를 다시 켠 뒤 재실행한 결과를 기준으로 했다.

## 기술 결정
- **내용 기반 추측은 하지 않는다.** 구현 전에 Pygments `guess_lexer`를 실험했더니 JavaScript 화살표 함수를 GDScript로, TypeScript를 GDScript로, Markdown을 T-SQL로, Java를 일반 텍스트로 판정했다. 틀린 이름이 저장되어 학습 문서에 노출되는 것보다 `unknown`이 낫다. 이 동작은 테스트로 고정했다(`.txt`에 JS 코드가 있어도 `text`, 확장자를 모르는 파일은 `unknown`).
- 확장자가 알려진 파일은 내용이 무엇이든 확장자가 이긴다(`app.js` 안에 파이썬 셔뱅이 있어도 javascript).
- Pygments 파일명 매칭은 대소문자를 구분하므로(`App.JSX` → 매칭 실패) 원래 이름으로 찾고 실패하면 소문자로 다시 찾는다.
- Pygments의 `code` 인자(내용으로 모호함 해소)는 쓰지 않는다. `.h`가 Objective-C로, `.m`이 Octave로 바뀌는 등 오히려 틀린 결과가 나왔다.
- Pygments가 `jsx`/`tsx`라고 부르는 것은 학습자에게는 JavaScript/TypeScript이므로 `javascript`/`typescript`로 바꾼다.
- 셔뱅은 첫 줄만, `env`의 옵션(`-S`)과 변수 대입(`VAR=1`)을 건너뛰고, 버전 숫자(`python3.11`)를 떼어 해석한다. 지원 인터프리터: python, node/nodejs, bash/sh/zsh/dash/ksh, ruby, perl, php.
- 상태가 없는 순수 함수라 클래스 대신 모듈 함수로 만들었다(DB 세션이 필요한 다른 서비스와 다름).
- Pygments는 pytest의 간접 의존성으로만 설치되어 있었다. `requirements.txt`에 직접 선언했다.

## 비고
- **붙여넣기 업로드**(T069, T078)는 파일명이 없으므로 사용자가 고른 언어를 `normalize_language()`로 정규화해 저장하면 된다. 알 수 없는 값(`None`)은 검증 오류로 처리해야 한다.
- **여러 파일**(폴더 업로드)의 대표 언어(`uploaded_code.detected_language` 한 칸)를 정하는 규칙(예: 줄 수가 가장 많은 언어)은 이 작업에 넣지 않았다. T069에서 정해야 한다.
- 이름 체계는 Pygments의 첫 번째 별칭에 의존한다. Pygments 버전이 올라 별칭이 바뀌면 지원 확장자 12개의 기대값 테스트가 바로 실패해 알려 준다.
- `.jsx`/`.tsx`를 각각 javascript/typescript로 묶었기 때문에 React 같은 프레임워크 정보는 이 값에 담기지 않는다.
- `ruff format --check`의 기존 지적(`tests/unit/test_token_service.py`)은 이번 작업과 무관하다.
