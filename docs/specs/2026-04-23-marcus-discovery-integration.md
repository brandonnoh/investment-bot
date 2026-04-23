# Marcus ↔ 발굴 페이지 통합 설계

**날짜**: 2026-04-23  
**목표**: 마커스 프롬프트 다이어트 + 분석 품질 향상 + 발굴 페이지 직접 연동

---

## 배경 & 문제

| 문제 | 원인 | 영향 |
|------|------|------|
| 마커스 프롬프트 390KB | fundamentals.json 680개 전체 (300KB) | 속도 저하, OS ARG_MAX 초과 위험 |
| 분석 품질 한계 | 후보 풀이 퀀트 기준 opportunities.json 하나 | RISK_OFF 레짐에서 방어주 후보 없음 |
| 발굴 연동 없음 | Marcus 추천 종목 → 발굴 페이지에서 수동 검색 | 사용자 경험 단절 |

---

## 설계

### 변경 범위

```
Python   — analysis/marcus_screener.py  (신규)
           scripts/run_marcus.py        (수정)
           docs/marcus/prompt.md        (수정)

Frontend — src/store/useMCStore.ts      (수정: 상태 추가)
           src/components/tabs/MarcusTab.tsx   (수정: 버튼 추가)
           src/components/tabs/DiscoveryTab.tsx (수정: 하이라이트)
```

---

### 1. `analysis/marcus_screener.py` (신규)

5개 전략을 실행해 B+(70점 이상) 통과 종목을 수집하고 Marcus 프롬프트용 compact JSON을 반환한다.

```python
# 반환 형태 (종목당 ~200자)
[
  {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "grade": "A",
    "strategies": ["버핏", "퀀트"],   # 통과한 전략 목록
    "composite_score": 0.83,
    "per": 28.5,
    "roe": 147.9,
    "operating_margin": 31.2,
    "revenue_growth": 5.1,
    "debt_ratio": 195.8
  }
]
```

**핵심 로직**:
1. 5개 전략(`composite`, `graham`, `buffett`, `lynch`, `greenblatt`) 각각 `run_strategy()` 호출
2. `composite_score >= 0.70` (B+) 종목만 수집
3. ticker 기준 중복 제거 — strategies 태그는 합산 (버핏+퀀트 동시 통과 → `["버핏", "퀀트"]`)
4. 핵심 재무 지표만 추출 (per/roe/opm/rev_growth/debt — 5개)
5. `_CACHE: dict` + `_CACHE_TTL = 3600` 으로 1시간 메모리 캐시

**예상 결과**: 680개 → 30~70개, 300KB → 10~15KB

---

### 2. `scripts/run_marcus.py` 수정

```python
# 제거
fundamentals = _load_json(INTEL_DIR / "fundamentals.json", "fundamentals")

# 추가
from analysis.marcus_screener import get_marcus_screened_pool
screened_pool = get_marcus_screened_pool()  # B+ 이상 종목들
```

`_assemble_prompt()` 시그니처: `fundamentals` → `screened_pool` 파라미터로 교체

---

### 3. `docs/marcus/prompt.md` 수정

**추가할 섹션** — 스크리닝 풀 안내 + 레짐별 전략 힌트:

```markdown
### 스크리닝 풀 (B+ 이상 통과 종목)
아래는 5개 전략 렌즈 중 하나 이상에서 B+(70점+) 이상을 받은 종목들이다.
`strategies` 필드는 어떤 거장 기준을 통과했는지를 나타낸다.

**레짐별 우선 렌즈 힌트**:
- RISK_OFF → 버핏·그레이엄 통과 종목 우선 (방어주·배당주)
- BULL     → 린치·그린블랫 통과 종목 우선 (성장주·모멘텀)
- NEUTRAL  → 퀀트(composite) 점수 순
```

---

### 4. 프론트엔드

#### 4-1. `useMCStore.ts` — 상태 추가

```typescript
// 추가할 상태
marcusPickedTicker: string | null
setMarcusPickedTicker: (ticker: string | null) => void
jumpToDiscovery: (ticker: string) => void  // setActiveTab('discovery') + setMarcusPickedTicker(ticker)
```

#### 4-2. `MarcusTab.tsx` — ticker 파싱 + 버튼

마커스가 출력하는 `### 눈여겨볼 종목` 섹션을 파싱해 각 종목에 버튼을 붙인다.

**파싱 전략**: Marcus가 눈여겨볼 종목을 출력할 때 ticker를 괄호 안에 포함하도록 prompt.md에서 강제한다.  
예: `1. **CNX Resources** (CNX, 72점) — 천연가스...`  
→ `\(([A-Z0-9.]+),` 정규식으로 ticker 추출 → 버튼 렌더링

```tsx
// 눈여겨볼 종목 한 줄 렌더 예시
<div className="flex items-center gap-2">
  <span>1. **CNX Resources** (72점) — 천연가스...</span>
  <button onClick={() => jumpToDiscovery('CNX')}
    className="text-[10px] px-2 py-0.5 rounded border ...">
    발굴에서 보기 →
  </button>
</div>
```

**구현 방식**: `### 눈여겨볼 종목` 이하 섹션을 raw 텍스트로 추출 → 줄별로 번호 목록 파싱 → 각 줄에 버튼 삽입 → 나머지 섹션은 기존 마크다운 렌더러 유지

#### 4-3. `DiscoveryTab.tsx` — 하이라이트

```typescript
const { marcusPickedTicker, setMarcusPickedTicker } = useMCStore()

// 1. marcusPickedTicker가 있으면 검색창에 자동 입력
// 2. 해당 종목 카드에 테두리 강조 (border-[#4dca7e])
// 3. 해당 카드로 자동 스크롤
// 4. 사용자가 전략 렌즈 변경하면 highlight 해제
```

Marcus에서 진입 시: 전략 렌즈를 `composite`로 고정하지 않고 **전체 전략 결과를 합산**해서 보여준다 — 해당 종목이 어떤 전략에서 발굴됐는지 무관하게 카드가 보여야 하기 때문. 검색 필터는 ticker 또는 name substring 매치. 사용자가 전략 렌즈 칩을 직접 클릭하면 `setMarcusPickedTicker(null)` 호출해 하이라이트 해제.

---

## 데이터 흐름 (변경 후)

```
매일 05:30 marcus 실행
  ├─ marcus_screener.get_marcus_screened_pool()
  │    └─ 5개 전략 → B+ 종목 30~70개 수집 (~15KB)
  ├─ news, macro, regime, supply, technical 로드
  └─ Claude 호출 (390KB → ~105KB)
       └─ "눈여겨볼 종목" 섹션 생성
              ↓
    MarcusTab 렌더링
      └─ 눈여겨볼 종목 파싱 → "발굴에서 보기 →" 버튼
              ↓ 클릭
    DiscoveryTab
      └─ 해당 종목 카드 하이라이트 + 스크롤
```

---

## 제외 범위

- `opportunities.json` 생성 파이프라인 변경 없음 (퀀트 composite 탭은 그대로)
- 발굴 페이지 자체 UX 변경 없음 (전략 렌즈 칩, 국장/미장 토글 그대로)
- Marcus SOUL.md 변경 없음

---

## 예상 효과

| 지표 | 전 | 후 |
|------|----|----|
| 마커스 프롬프트 크기 | ~390KB | ~105KB |
| fundamentals 데이터 | 680개 전체 | B+ 30~70개 |
| 후보 풀 전략 커버리지 | 퀀트 1개 | 5개 전략 통합 |
| 발굴 페이지 연동 | 없음 | 원클릭 이동 + 하이라이트 |
