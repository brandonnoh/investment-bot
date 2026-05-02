# web-next 프론트엔드 — 온보딩 가이드

## 기술 스택

| 패키지 | 버전 | 용도 |
|--------|------|------|
| Next.js | 16.2.4 | App Router, standalone 빌드 |
| React | 19.2.4 | UI |
| TypeScript | 5 | 타입 |
| Tailwind CSS | 4 | 스타일 (PostCSS 기반, config 파일 없음) |
| Zustand | 5 | 전역 상태 |
| SWR | 2 | 데이터 페칭 + 캐시 |
| Recharts | 3 | 차트 |
| shadcn/ui | 4 (Base UI) | UI 컴포넌트 기반 |
| sonner | 2 | 토스트 알림 |
| react-markdown | 10 | 마크다운 렌더링 (Marcus 분석) |

> ⚠️ **이 Next.js는 16.x다 — App Router 전용.** `pages/` 없음. `params`는 `Promise<{...}>` 타입이다.

---

## 프로젝트 구조

```
web-next/
├── src/
│   ├── app/
│   │   ├── page.tsx                  # 메인 SPA (SSEProvider + 탭 렌더링)
│   │   ├── layout.tsx
│   │   ├── globals.css               # Tailwind 4 테마 + mc-* 커스텀 컬러
│   │   └── api/[...path]/route.ts    # Flask 프록시 (SSE·스트리밍 특별처리)
│   ├── store/
│   │   └── useMCStore.ts             # Zustand 전역 상태
│   ├── hooks/                        # SWR 래퍼 훅
│   ├── components/
│   │   ├── Header.tsx                # 헤더 (파이프라인 실행 버튼, SSE 상태)
│   │   ├── TabNav.tsx                # 탭 네비게이션 (메인 5 + 추가 6)
│   │   ├── SSEProvider.tsx           # useSSE 마운트 래퍼
│   │   ├── tabs/                     # 탭 컴포넌트 (11개)
│   │   ├── discovery/                # 기업 상세 드로어 (CompanyDrawer)
│   │   ├── advisor/                  # AI 어드바이저 패널, 자산 그리드
│   │   ├── charts/                   # 차트 컴포넌트
│   │   └── ui/                       # shadcn/ui 기반 공통 컴포넌트
│   ├── lib/
│   │   ├── api.ts                    # fetcher 함수 모음
│   │   ├── format.ts                 # fmtKrw, fmtPct, fmtAmt, pctColor
│   │   └── savedStrategies.ts        # 어드바이저 전략 CRUD (서버 저장)
│   ├── types/
│   │   ├── api.ts                    # Flask 응답 타입 (IntelData, PriceItem 등)
│   │   └── advisor.ts                # InvestmentAsset, RiskLevel, LoanConfig 등
│   └── data/
│       └── investment-assets.json    # 투자 자산 정의 (어드바이저용)
├── next.config.ts                    # output: standalone, 캐시 헤더
└── package.json
```

---

## 탭 구성 (11개)

**메인 탭** (TabNav 상단):

| TabId | 컴포넌트 | 역할 |
|-------|----------|------|
| `overview` | OverviewTab | 시장 개요, 매크로, 레짐 |
| `portfolio` | PortfolioTab | 보유 종목, 수익률, 섹터 비중 |
| `wealth` | WealthTab | 전재산 (투자+비금융 자산) |
| `marcus` | MarcusTab | Marcus AI 분석 리포트 |
| `discovery` | DiscoveryTab | 종목 발굴 (퀀트/그레이엄/버핏/린치/그린블랫) |

**추가 탭** (더보기 메뉴):

| TabId | 컴포넌트 | 역할 |
|-------|----------|------|
| `solar` | SolarTab | 태양광 매물 목록 |
| `advisor` | AdvisorTab | AI 투자 어드바이저 |
| `saved-strategies` | SavedStrategiesTab | 저장된 AI 전략 |
| `alerts` | AlertsTab | 투자 알림 |
| `system` | SystemTab | 파이프라인 로그, 시스템 상태 |
| `service-map` | ServiceMapTab | 서비스 구조 시각화 |

---

## 전역 상태 (useMCStore)

```typescript
// src/store/useMCStore.ts
interface MCStore {
  activeTab: TabId            // URL ?tab= 우선, 없으면 localStorage 폴백
  pipelineRunning: boolean
  marcusRunning: boolean
  sseStatus: 'connected' | 'disconnected'
  lastUpdated: string
  marcusPickedTicker: string | null  // Marcus가 선택한 종목 → discovery 이동용
  // actions
  setActiveTab(tab): void    // localStorage + URL querystring 동기화
  jumpToDiscovery(ticker): void  // discovery 탭으로 이동 + ticker 설정
}
```

**탭 전환 규칙:** `setActiveTab` 호출 시 `?tab=xxx` URL 쿼리스트링 자동 동기화.

---

## 데이터 페칭 (SWR 훅)

| 훅 | SWR 키 | 갱신 방식 | 설명 |
|----|--------|-----------|------|
| `useIntelData` | `intel-data` | SSE 트리거 (폴링 없음) | `/api/data` 전체 통합 데이터 |
| `useProcessStatus` | `process-status` | 5초 폴링 + SSE 트리거 | 파이프라인/Marcus 실행 상태 |
| `useMarcusLog` | `marcus-log` | 3초 폴링 (enabled일 때만) | Marcus 로그 |
| `useOpportunities` | `opportunities-{strategy}` | 5분 deduping | 종목 발굴 (전략별) |
| `useWealthData` | `/api/wealth` | 1분 폴링 | 전재산 데이터 |
| `useAnalysisHistory` | `analysis-history` | 기본값 (onMount) | Marcus 분석 이력 |

**SSE 흐름:**
```
Flask /api/events → useSSE (SSEProvider)
  → mutate('intel-data')     // 인텔 데이터 즉시 갱신
  → mutate('process-status') // 파이프라인 상태 즉시 갱신
  → setLastUpdated(시각)
```

---

## Flask 프록시 (route.ts)

`src/app/api/[...path]/route.ts` — 모든 `/api/*` 요청을 Flask(기본 `:8421`)로 프록시.

**특별 처리:**
- `/api/events` → SSE 스트림 패스스루 (`text/event-stream`)
- `/api/investment-advice-stream` → AI 어드바이저 스트리밍 SSE 패스스루
- 그 외 → 일반 JSON 프록시 (GET/POST/PUT/DELETE)

**환경변수:**
```
PYTHON_API_URL=http://localhost:8421   # Flask API 주소 (컨테이너 내부)
NEXT_PUBLIC_API_BASE=                  # 개발 모드에서 로컬 Flask 직접 연결 시
```

---

## 어드바이저 전략 저장 (savedStrategies.ts)

전략은 **서버 DB에 저장**한다 (`localStorage` 아님).

```
GET  /api/advisor-strategies?limit=20  → SavedStrategy[]
POST /api/advisor-strategies           → { id }
DELETE /api/advisor-strategies/{id}
```

`SavedStrategy` 구조: `id, saved_at, capital, leverage_amt, risk_level, recommendation, loans_json, monthly_savings`
`loans_json`은 `SavedLoan[]`을 JSON 직렬화한 문자열.

---

## localStorage 키

| 키 | 내용 |
|----|------|
| `mc-active-tab` | 마지막 활성 탭 |
| `mc-advisor-settings` | `capital, riskLevel, minusLoan, creditLoan, monthlySavings, portfolioMode` |
| `solar_read_v1` | 태양광 읽음 상태 (listing_id Set) |
| `solar_starred_v1` | 태양광 즐겨찾기 (listing_id Set) |

---

## 커스텀 컬러 (Tailwind 클래스)

`globals.css`의 `@theme inline`에 정의:

| 클래스 | 용도 |
|--------|------|
| `bg-mc-bg` | 앱 배경 (라이트: `#f8f6f3`, 다크: `#0c0b0a`) |
| `bg-mc-card` | 카드 배경 |
| `border-mc-border` | 카드 테두리 |
| `text-mc-green` | 수익/양수 (`#4dca7e`) |
| `text-mc-red` | 손실/음수 (`#e05656`) |
| `text-gold` / `border-gold` | 골드 강조색 (`#c9a93a`) |
| `text-amber` | 경고/중립 (`#e09b3d`) |

폰트: `font-sans` = Space Grotesk, `font-mono` = JetBrains Mono.

---

## 유틸 함수 (lib/format.ts)

```typescript
fmtKrw(v)   // 천단위 콤마 (예: 47,312,450)
fmtPct(v)   // 부호 포함 % (예: +1.23%)
fmtAmt(v)   // 억/만 단위 (예: 1.5억, 3,500만)
pctColor(v) // 값에 따라 text-mc-green / text-mc-red / text-muted-foreground
```

---

## 주요 타입 (types/api.ts)

- `IntelData` — `/api/data` 응답 최상위 타입 (portfolio_summary, prices, macro, alerts, regime, ...)
- `PriceItem` — 종목 가격 + 보유 종목 확장 필드
- `CompanyProfile` — `/api/company?ticker=` 응답 (기업 상세, 뉴스, 애널리스트 리포트)
- `SolarListing` / `SolarResponse` — 태양광 매물
- `ProcessStatus` — `{ pipeline: { running }, marcus: { running } }`

---

## 빌드 & 배포

```bash
# 개발
cd web-next && npm run dev

# 프로덕션 빌드
cd web-next && npm run build
# → .next/standalone/ 생성

# Docker 배포 (반드시 이 순서)
docker exec mc-web rm -rf /app/.next/static/   # 구버전 청크 삭제 필수
docker cp web-next/.next/standalone/. mc-web:/app/
docker cp web-next/.next/static/. mc-web:/app/.next/static/
docker restart mc-web
```

> ⚠️ `rm -rf /app/.next/static/` 생략 금지 — docker cp는 추가만 하므로 구버전 JS chunk가 남는다.

---

## 새 탭 추가 체크리스트

1. `src/store/useMCStore.ts` — `TabId` 유니온에 추가
2. `src/components/TabNav.tsx` — `MAIN_TABS` 또는 `EXTRA_TABS` 배열에 추가
3. `src/components/tabs/` — 탭 컴포넌트 파일 생성
4. `src/app/page.tsx` — import + `activeTab === 'xxx'` 조건부 렌더링 추가

## 새 API 엔드포인트 호출 체크리스트

1. `src/lib/api.ts` — fetcher 함수 추가
2. `src/hooks/` — SWR 훅 추가 (필요 시)
3. `src/types/api.ts` — 응답 타입 추가
