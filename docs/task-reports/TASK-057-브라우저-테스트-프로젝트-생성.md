# TASK-057: 브라우저 테스트 — 새 프로젝트 생성 후 대시보드 표시

## 상태
완료

## 날짜
2026-11-10

## 작업 요약
새 프로젝트를 만들면 대시보드 목록에 나타나는지 실제 브라우저(Playwright, Chromium)로 확인했다. 수동 테스트 대신 재실행 가능한 E2E 스펙으로 자동화했다.

## 변경 파일
- `frontend/e2e/projects.spec.ts` (신규, 테스트 4개 공통)
- `frontend/playwright.config.ts` (신규)
- `frontend/package.json` (`@playwright/test` devDependency, `test:e2e` 스크립트)
- `.gitignore` (`e2e/.results/`)

## TDD 결과
- 검증 항목: 빈 대시보드 문구 표시 → "새 프로젝트" 모달에서 제목·설명 입력 후 "만들기" → 목록에 제목과 설명 표시 → 새로고침 후에도 유지.
- 결과: 통과. 기존 vitest 314개, eslint, build도 그대로 통과.

## 기술 결정
- 개발 서버(5173/8000)와 개발 DB를 그대로 사용하고, 실행마다 고유한 이메일의 임시 계정을 만든다. 종료 시 `users` 행을 삭제하면 프로젝트도 CASCADE로 함께 지워지며, 삭제 후 0건임을 스펙이 직접 확인한다.
- 요청은 Playwright MCP였으나 이 세션에 없어서 `@playwright/test`를 직접 사용했다. 연결된 Chrome 확장은 localhost를 열지 못했다.

## 비고
- 임시 계정 비밀번호는 실행 시각으로 생성되며 저장하지 않는다.
