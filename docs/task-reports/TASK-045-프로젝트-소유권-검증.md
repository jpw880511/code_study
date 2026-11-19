# TASK-045. 프로젝트 소유권 검증

## 상태
완료

## 날짜
2026-11-09

## 작업 요약
"남의 서랍은 못 연다"는 규칙입니다. `ProjectService._owned_active_project(user_id, project_id)` **한 곳**에서 검사하고 `get`/`update`/`soft_delete`가 모두 이것을 씁니다.

| 프로젝트 상태 | 결과 |
|---|---|
| 없음 | `project_not_found` (404) |
| 휴지통 (본인이든 타인이든) | `project_not_found` (404) |
| 활성 + 다른 사용자 소유 | `project_forbidden` (403) |
| 활성 + 본인 소유 | 통과 |

- 순서: 존재/휴지통 확인 → 소유자 확인 → (수정이면) 입력 검증. 따라서 남의 프로젝트에 잘못된 값을 보내도 403이 먼저입니다.
- 오류 메시지와 args에는 프로젝트 제목/설명/ID/소유자 ID가 없음(정보 노출 방지).

## 변경 파일
- `backend/src/services/project_service.py` (T044 파일에 포함), `backend/tests/integration/test_project_service_db.py` (소유권 행렬 테스트)

## TDD 결과
- RED: 소유권 행렬 테스트를 서비스 테스트에 먼저 작성 → 서비스 모듈 부재로 수집 실패 확인(T044와 같은 RED)
- GREEN: 구현 후 통과. get/update/delete × (본인 / 남의 활성 / 없음 / 본인 휴지통 / 남의 휴지통) 전부 검증, 거부된 호출은 DB를 바꾸지 않음을 확인
- REFACTOR: 검사를 `_owned_active_project` 한 곳으로 모음
- RED/GREEN/REFACTOR 커밋: 해당 없음 (Git 저장소 아님)
- 테스트 커버리지: `src/` 100%

## 기술 결정
- **휴지통 프로젝트는 모두에게 404.** 남의 휴지통 프로젝트에 403을 주면 "그 ID가 존재했다"는 사실이 새어 나가므로 존재하지 않는 것과 구분하지 않음.
- **존재하지만 남의 활성 프로젝트는 403**(지시 사항). 이 경우 ID가 존재한다는 사실은 알려지지만 내용은 전혀 노출되지 않음. UUID라 추측이 사실상 불가능하다는 점에 의존하는 설계입니다. 더 엄격하게 하려면 403 대신 404로 통일하면 되며, `_owned_active_project`만 고치면 됩니다.

## 비고
- 다음 작업: T046~T050 (API).
