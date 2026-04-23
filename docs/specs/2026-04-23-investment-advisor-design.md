# 투자 어드바이저 페이지 설계

**날짜:** 2026-04-23  
**상태:** 설계 완료, 구현 승인 대기

---

## 개요

자본금 + 레버리지 기반으로 접근 가능한 투자 유형 전체를 보여주고,  
현재 포트폴리오에서 리스크 성향을 AI가 자동 추론하여 개인 맞춤 어드바이징을 제공하는 대시보드 탭.

---

## 화면 구조 (3-panel layout)

```
┌─ Panel 1: 내 조건 (상단 고정) ────────────────────────────────────────┐
│  자본금   [DB 자동: 3.2억]  ←─────슬라이더──────→  직접 조정          │
│  레버리지 [포함 ON ●        OFF]                                       │
│  리스크   [AI추론: 중립]    ←─────슬라이더──────→  보수 ←→ 공격      │
│           └ "주식 60% 집중 → 중립 추정" (한 줄 근거)                  │
└────────────────────────────────────────────────────────────────────────┘
┌─ Panel 2: AI 어드바이저 (중단) ───────────────────────────────────────┐
│  지금 내 조건이라면: 주식 30% + 리츠 40% + 채권 30%                  │
│  근거: 금리 2.5% 환경에서 배당 자산 우위, 주식은 방산/AI 섹터 집중  │
│                                              [분석 갱신 ↺]            │
└────────────────────────────────────────────────────────────────────────┘
┌─ Panel 3: 투자처 목록 (하단 실시간 필터) ─────────────────────────────┐
│  [정렬: 수익률↓ | 리스크↑ | 최소자본↑]  [카테고리 필터 칩]           │
│                                                                        │
│  ✓ 가능  ✗ 자본부족  △ 조건부  🔜 출시예정                            │
│                                                                        │
│  ┌ KRX 금 ✓ ┐  ┌ 상장 리츠 ✓ ┐  ┌ 주식/ETF ✓ ┐  ┌ 채권 ✓ ┐       │
│  │세금 0원   │  │배당 7~9%   │  │레버리지 2x │  │5.4~7.4%│       │
│  │최소 15만원│  │최소 수천원 │  │최소 수만원 │  │최소 1천 │       │
│  │리스크 ★★☆│  │리스크 ★★☆ │  │리스크 ★★★ │  │리스크 ★★│       │
│  └──────────┘  └────────────┘  └────────────┘  └─────────┘       │
│                                                                        │
│  ┌ 아파트 ✗ ┐  ┌ 태양광 △ ┐   ┌ STO 🔜 ┐    ┌ 탄소배출권 ✓ ┐   │
│  │최소 3억  │  │RPS폐지예정│   │2027 시행│    │KRX 장내   │   │
│  │자본 부족 │  │자기자본3천│   │예정     │    │최소 수만원│   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 투자 자산 데이터 (정적 JSON, 40개 유형)

### 카테고리 구분

| 카테고리 | 유형 수 | 코드 |
|---------|--------|------|
| 전통금융 | 10 | `finance` |
| 부동산 | 8 | `realestate` |
| 파생/레버리지 | 5 | `derivatives` |
| 대체투자 | 8 | `alternative` |
| 사모/전문투자 | 5 | `private` |
| 에너지/인프라 | 3 | `energy` |
| 크라우드펀딩 | 3 | `crowd` |

### 각 자산 항목 스키마

```typescript
interface InvestmentAsset {
  id: string
  name: string                    // "KRX 금시장"
  category: CategoryCode
  min_capital: number             // 최소 진입 자본 (원)
  min_capital_with_leverage: number | null
  expected_return_min: number     // 연 수익률 하한 (%)
  expected_return_max: number     // 연 수익률 상한 (%)
  risk_level: 1 | 2 | 3 | 4 | 5
  liquidity: 'instant' | 'days' | 'weeks' | 'months' | 'years'
  leverage_available: boolean
  leverage_ratio: number | null   // 최대 배수
  tax_benefit: string | null      // "세금 0원", "ISA 편입 가능" 등
  regulation_note: string | null  // 규제/자격 요건
  status: 'available' | 'restricted' | 'upcoming' // upcoming = STO 등
  upcoming_date: string | null    // "2027-01"
  beginner_friendly: boolean
  description: string             // 한 줄 설명
  caution: string | null          // 주의사항 (RPS 폐지 등)
  leverage_type: string | null    // "주택담보대출 LTV70%", "신용융자 2.5배" 등
}
```

### 자본금 접근 가능 여부 계산 로직

```
available:   min_capital <= 자본금
             OR (leverage_available AND min_capital_with_leverage <= 자본금 AND 레버리지_토글_ON)
restricted:  위 조건 불충족
conditional: 자격 요건 있음 (전문투자자, 농지법 등)
upcoming:    status === 'upcoming'
```

---

## 데이터 소스

| 데이터 | 소스 | 방식 |
|-------|------|------|
| 자본금 | `GET /api/wealth` → `total_wealth_krw` | 자동 (DB) + 슬라이더 오버라이드 |
| 리스크 추론 | `GET /api/data` → `portfolio.holdings` | 프론트 계산 (주식 비중 기준) |
| 투자처 목록 | `investment_assets.json` (정적) | 빌드 타임 번들 or fetch |
| AI 어드바이저 | `POST /api/investment-advice` | 온디맨드 Claude 호출 |

---

## 리스크 성향 자동 추론 로직 (프론트)

```typescript
function inferRiskProfile(holdings: Holding[]): { level: number; reason: string } {
  const stockRatio = holdings.filter(h => !h.asset_type || h.asset_type === 'stock')
    .reduce((sum, h) => sum + h.weight, 0)
  
  if (stockRatio >= 0.8) return { level: 4, reason: '주식 80%+ 집중 → 공격 추정' }
  if (stockRatio >= 0.6) return { level: 3, reason: `주식 ${Math.round(stockRatio*100)}% 집중 → 중립 추정` }
  if (stockRatio >= 0.4) return { level: 2, reason: '주식/채권 혼합 → 보수-중립 추정' }
  return { level: 1, reason: '현금/채권 위주 → 보수 추정' }
}
```

슬라이더로 오버라이드 가능. 슬라이더 조작 시 AI 추론 뱃지 → "직접 설정"으로 변경.

---

## AI 어드바이저 API

### 요청
```
POST /api/investment-advice
{
  "capital": 320000000,
  "leverage": true,
  "risk_level": 3,          // 1=보수 ~ 5=공격
  "risk_reason": "주식 60% 집중",
  "available_assets": ["krx-gold", "reits", "stock-etf", ...]
}
```

### Flask 엔드포인트
- 프롬프트: 자본금 + 리스크 + 가능 자산 목록 + 2026 시장 컨텍스트
- Claude API 호출 (streaming 불필요, 300자 이내 응답)
- 응답: `{ recommendation: string, allocations: [{asset, ratio}] }`

### Marcus와 공유 패턴
Marcus처럼 `marcusRunning` 대신 `advisorLoading` 상태로 로딩 UI 처리.

---

## 컴포넌트 구조

```
AdvisorTab
├── ConditionPanel          (자본금/레버리지/리스크 입력)
│   ├── CapitalSlider
│   ├── LeverageToggle
│   └── RiskSlider
├── AIAdvisorPanel          (AI 추천 + 갱신 버튼)
└── AssetGrid               (실시간 필터된 카드 목록)
    ├── CategoryFilter       (칩 필터)
    ├── SortControl
    └── AssetCard[]
        ├── StatusBadge      (✓ / ✗ / △ / 🔜)
        ├── ReturnRange
        ├── RiskStars
        ├── LiquidityIcon
        └── LeverageInfo
```

---

## 탭 추가

기존 탭 순서:
```
마커스 | 발굴 | 포트폴리오 | 자산 | 태양광 | 알림 | 어드바이저* | 시스템
```
`*` 신규 추가

---

## 구현 범위 (스코프)

### IN 스코프
- Panel 1: 자본금(DB자동+슬라이더) + 레버리지 토글 + 리스크(AI추론+슬라이더)
- Panel 2: AI 어드바이저 (텍스트 추천 + 갱신 버튼)
- Panel 3: 40개 자산 카드 그리드 + 실시간 필터 + 카테고리 칩
- `investment_assets.json` 정적 데이터 파일
- `/api/investment-advice` Flask 엔드포인트

### OUT 스코프 (향후)
- 자산별 상세 페이지 (링크/드릴다운)
- 과거 수익률 차트
- 자산 간 포트폴리오 시뮬레이터
- 실시간 금리/환율 연동

---

## 셀프리뷰 체크

- [x] 플레이스홀더 없음
- [x] 컴포넌트-데이터-API 삼각 일관성 확인
- [x] 스코프 단일 구현 계획 가능
- [x] 리스크 추론 로직 명시
- [x] 40개 자산은 `investment_assets.json`으로 관리 (코드 하드코딩 없음)
