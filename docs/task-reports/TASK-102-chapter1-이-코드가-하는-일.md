# TASK-102. T102 `Chapter1` (이 코드가 하는 일)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
1장 제목(h3)과 요약(`summary`)을 일반 텍스트로 보여 줍니다. `whitespace-pre-wrap`으로 줄바꿈을 유지합니다. 모든 챕터 컴포넌트와 같이 문서 텍스트는 React 텍스트 노드로만 그리고 `dangerouslySetInnerHTML`은 쓰지 않습니다(`src` 전체에서 0건 확인).

## 변경 파일
- `frontend/src/components/document/chapters/Chapter1.tsx` (생성)
- `frontend/tests/unit/document-chapters.test.tsx` (7개 챕터 공용 테스트 파일, 생성)

## TDD 결과
- RED: 챕터 모듈이 없어 테스트 파일이 실패하는 것을 확인했습니다.
- GREEN: 제목/요약 표시, 그리고 `<div id="x">`, `<script>`, `a < b`가 그대로 텍스트로 보이고 DOM 요소로 생기지 않는 것을 확인했습니다.
- 전체 506개 통과.

## 기술 결정
- 챕터 제목은 계약에서 "고정"이지만 서버가 준 `title`을 그대로 보여 줍니다(하드코딩하지 않음).

## 비고
- 없음.
