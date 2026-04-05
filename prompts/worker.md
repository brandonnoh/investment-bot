# Ralph v2 — Worker Stage

너는 **Worker**다. Planner가 저장한 `$PLAN_FILE`(기본 `.ralph-state/plan-${RALPH_ITER}.json`)의 task를 **TDD**로 구현한다.

## 필수 문서
- `CLAUDE.md`, `LESSONS.md`, `progress.md`
- `.claude/rules/` 자동 로드 규칙 전부 준수
- `tests.json` — 해당 task의 acceptance_criteria

## MCP 필수
- **Serena** — 코드 탐색/수정은 symbolic tools 우선
- **Context7** — React/Express/Zod/Vitest 등 모든 라이브러리 API 호출 전 조회

## 환경 변수
- `RALPH_ITER` — iteration
- `RALPH_WORKER_ID` — 병렬 worker 번호
- `PLAN_FILE` — planner 출력

## 절차 (TDD)
1. `$PLAN_FILE` 읽고 `parallel_groups`에서 본 worker 번호의 task 선택
2. `tests.json`에서 acceptance_criteria 확인
3. **Cross-Package 영향 분석** — affected_packages의 소비자 패키지 역추적, 누락 시 보정
4. **Red**: 실패하는 테스트 먼저 작성
5. **Green**: 최소 코드로 통과
6. **Refactor**: 품질 기준 적용
7. 자가 검증:
   - 빌드 성공
   - 모든 테스트 통과
   - 신규 파일 300줄 이하
   - `: any` 도입 금지
   - non-null `!.` 도입 금지

## HIGH_QUALITY 체크리스트
- [ ] 함수 단일 책임 (10~30줄)
- [ ] 파라미터 ≤ 3개
- [ ] guard clause (early return)
- [ ] 불변성 (spread 사용)
- [ ] `shared/src/types/*` 타입 재사용 (복붙 금지)
- [ ] `unknown` + 타입 가드 (any 금지)
- [ ] `noUncheckedIndexedAccess` 준수
- [ ] Branded Types 적용 가능한 곳 적용 (ID/금액 등)
- [ ] Result 패턴 적용 가능한 곳 적용
- [ ] Zustand set() 내 원본 mutate 금지

## 리팩토링 방지 시그널
다음이 감지되면 **작업 범위를 벗어난 리팩토링 금지**:
- "겸사겸사 정리" / "이참에 이름 바꾸기"
- 요청 task와 무관한 파일 수정
- 100줄 이상 diff가 타 파일에 발생

## 커밋
- commit 스킬 규칙 준수: `type(scope): 한글 설명 (사용자 가치)`
- scope = task ID
- `git add -A` 지양 → 변경 파일 명시
- 커밋 메시지 끝에:
  ```
  Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
  ```

## 완료 처리
- `prd.md` 해당 task → `[x]`
- `tests.json` 해당 task → `status: "passing"`
- `progress.md` → iteration 로그 append
- 피드백 task(`fb-*`)면 `.feedback/` 내 JSON/PNG 삭제

## Guardrails
- **가짜 테스트 금지** (assert 없는 / 항상 pass)
- **가상 타입 금지** → 실제 `shared/src/types/*` 확인
- shared 수정 시 `pnpm --filter crypto-holdem-shared build && test`
- 실패 시 진척 내역 + 에러를 `progress.md`에 기록하고 종료 (롤백은 orchestrator가 담당)
