# TASK-107. T107 DocumentViewer 로딩 상태 (`DocumentStatusView`)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
문서가 보이기 전 상태를 `DocumentStatusView`가 보여 줍니다(FR-024).

- 문서 없음(404 `document_not_found`) -> "아직 학습 문서가 없습니다."
- `pending` -> "문서 생성을 기다리는 중"(`role="status"`)
- `in_progress` -> "문서를 만드는 중입니다." + 진행 표시줄(`role="progressbar"`, 이름 "문서 생성 진행률", `aria-valuemin=0`, `aria-valuemax=100`, `aria-valuenow`) + 남은 시간. 남은 시간은 `max(0, estimated_total_seconds - elapsed_seconds)`(서버가 계산한 경과 시간 사용, 브라우저 시계 미사용): "약 N초 남음", 0이면 "곧 완료됩니다".
- `notice`가 있으면 `pending`/`in_progress` 둘 다에서 표시합니다.
- `failed` -> `error` 문구를 `role="alert"`로(없으면 "문서를 만들지 못했습니다."). **다시 시작 버튼은 없습니다**(범위 밖).

## 변경 파일
- `frontend/src/components/document/DocumentStatusView.tsx` (생성)
- `frontend/tests/unit/DocumentStatusView.test.tsx` (생성, 10개)
- 뷰어 통합은 `DocumentViewer.test.tsx`(TASK-105)에서 검증

## TDD 결과
- RED: 모듈 없음으로 실패 확인. GREEN: 10개 통과(문서 없음, pending, notice, 진행 표시줄의 값 속성과 "약 15초 남음", 추정 초과 시 음수 없이 "곧 완료됩니다", 정확히 0초, 서버가 시간을 안 준 경우 값·시간 문구 없음, 재시도 안내, 실패 alert와 버튼 없음, 오류 문구 없을 때 대체 문구).
- 뷰어 통합(가짜 타이머): 진행 중 -> 약 16초 남음 -> 2초 뒤 약 14초 남음 -> 완료되면 문서 표시.
- 전체 506개 통과.

## 기술 결정
- 진행률은 `경과/추정`을 반올림하되 진행 중에는 최대 99%로 제한합니다. 추정은 대략적이라 100%인데 계속 기다리면 고장처럼 보이기 때문입니다. 시간 값이 없으면 `aria-valuenow`를 생략합니다(불확정 진행).
- 남은 시간은 폴링(2초) 때마다만 갱신되고 브라우저에서 따로 1초씩 줄이지 않습니다(서버 값만 신뢰하라는 지침).

## 비고
- "대기열에서 기다리는 중" 때는 시간을 보여 주지 않습니다(`elapsed_seconds`는 `in_progress`일 때만 계약상 값이 있음).
