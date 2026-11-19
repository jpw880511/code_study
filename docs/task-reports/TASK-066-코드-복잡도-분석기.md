# TASK-066: 코드 복잡도 분석기

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
업로드된 코드의 난이도를 beginner / intermediate / advanced로 평가하는 분석기를 만들었다(FR-021). 줄 수, 함수 개수, 블록 중첩 깊이 세 가지를 재고(research.md), 가장 까다로운 지표가 등급을 정한다. 파일 하나를 재는 `measure_source()`와 업로드 전체(여러 파일)를 평가하는 `assess()`로 나뉜다. DB나 파일시스템에는 접근하지 않는다.

## 변경 파일
- `backend/src/services/code_analysis/complexity_analyzer.py` (신규)
- `backend/tests/unit/test_complexity_analyzer.py` (신규, 35개)

## 제공 함수
| 함수 | 역할 |
|---|---|
| `measure_source(content, language)` | 한 파일의 `FileMetrics(language, lines, functions, max_depth)` |
| `classify_level(lines, functions, depth)` | 세 수치로 등급 결정 |
| `assess(files)` | 여러 파일을 합쳐 `ComplexityReport(level, total_lines, code_lines, function_count, max_depth)` |

`language`는 `language_detector`(T065)가 돌려준 이름이나 `normalize_language()`의 결과를 그대로 넘긴다.

## 등급 기준 (제가 정한 값 — 명세에는 수치가 없다)
| 등급 | 조건 |
|---|---|
| beginner | 줄 ≤ 100 **그리고** 함수 ≤ 5 **그리고** 깊이 ≤ 4 |
| advanced | 줄 > 300 **또는** 함수 > 15 **또는** 깊이 > 6 |
| intermediate | 그 사이 |

- 깊이 4는 "클래스 → 메서드 → 반복문 → if"까지를 초급으로 본다는 뜻이다. 최상위 코드는 깊이 0.
- 줄 수는 비어 있지 않은 줄이다. 300줄 기준은 FR-025의 "일반적인 작업 500줄" 아래에 두었다.
- 값은 모듈 상단 상수라 한 곳에서 바꿀 수 있고, 경계값 테스트가 어느 경계가 움직였는지 알려 준다.

## TDD 결과
- RED: 모듈이 없어 `ImportError`로 수집 단계에서 실패.
- GREEN: 신규 35개 통과. 전체 894개 통과(건너뜀 0), 커버리지 100%(1054문장, 미커버 0). `ruff check`, `mypy src` 통과.
- 등급 경계(100/101줄, 5/6함수, 4/5깊이, 300/301줄, 15/16함수, 6/7깊이)를 모두 테스트로 고정했고, 등급 이름이 DB의 `uploaded_code_complexity_level_check`와 같은지 대조하는 테스트가 있다.
- 실제 파일 확인: `file_validator.py`(124줄, 함수 9, 깊이 2) → intermediate, `api/*.py` 폴더(404줄) → advanced.

## 기술 결정
- **문자열·주석 안의 `def`, `function`, `{`는 세지 않는다.** 텍스트 검색이 아니라 토큰으로 센다: 중괄호 언어는 Pygments 토큰, Python은 `tokenize`(INDENT/DEDENT).
- Python 깊이를 `tokenize`로 재므로 독스트링 안의 깊은 들여쓰기가 깊이를 부풀리지 않는다(테스트로 고정). 문법 오류가 있는 코드(학습자 코드는 틀릴 수 있다)는 예외를 던지지 않고 오류 지점 전까지 잰 값을 쓴다.
- 함수 개수: Python은 `def`(async 포함, lambda 제외), Java/C/C++는 Pygments가 함수 정의로 표시한 이름, JavaScript/TypeScript는 `function` 키워드와 `=>`. Pygments가 JS/TS 함수를 태그하지 않기 때문이다.
- **성능 상한**: Pygments는 1MB에 약 1.5~2초가 걸려 10MB 업로드는 요청 중 20초 안팎이 된다. 앞쪽 500,000자까지만 분석한다(`MAX_ANALYZED_CHARS`). 줄 수는 전체를 센다. 이만큼 긴 파일은 줄 수만으로 이미 advanced라 등급은 바뀌지 않고, 함수·깊이는 하한값이 된다.
- 문서(markdown, text, unknown)는 전체 줄 수(`total_lines`)에는 넣고 난이도 계산(`code_lines`)에서는 뺀다. 900줄짜리 README가 코드를 advanced로 만들지 않도록 하기 위해서다. 코드가 하나도 없는 업로드는 beginner로 본다.
- 여러 파일이면 줄 수·함수는 합산하고 깊이는 가장 깊은 파일을 쓴다. 작은 파일 8개(320줄)가 모이면 advanced가 된다.

## 비고 (한계)
- JavaScript/TypeScript의 **클래스 메서드는 함수 수에서 빠진다**(하한값). C++ 클래스 안에 정의한 메서드도 마찬가지다.
- 깊이는 코드 블록이 아니라 중괄호를 센다. JSX의 `{...}` 표현식도 한 단계로 세어져, 53줄짜리 React 페이지(`Dashboard.tsx`)가 깊이 5로 intermediate가 된다. Java처럼 클래스가 감싸는 언어는 기본 깊이가 1~2 높다.
- 테스트 파일처럼 짧은 함수가 많은 코드는 함수 수 때문에 advanced가 될 수 있다(155줄, 함수 22개).
- HTML은 줄 수만 반영하고 태그 중첩은 재지 않는다. Ruby, bash처럼 표가 없는 언어도 줄 수만 반영한다.
- 이 기준이 학습 난이도와 잘 맞는지는 실제 업로드가 쌓인 뒤 조정이 필요할 수 있다.
- `ruff format --check`의 기존 지적(`tests/unit/test_token_service.py`)은 이번 작업과 무관하다.
