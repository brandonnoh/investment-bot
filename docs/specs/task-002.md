# task-002: API 타입 정의 + SWR 데이터 훅

## 배경
Flask API(`/api/data`, `/api/status`, `/api/events` 등)의 응답 구조를 TypeScript 타입으로 정의하고, SWR 기반 훅으로 감싼다.

## 현재 Flask API 엔드포인트 (web/api.py 기준)

| 엔드포인트 | 메서드 | 응답 |
|-----------|--------|------|
| `/api/data` | GET | IntelData 전체 |
| `/api/status` | GET | 프로세스 상태 |
| `/api/events` | GET | SSE 스트림 |
| `/api/run-pipeline` | POST | `{ok: true}` |
| `/api/run-marcus` | POST | `{ok: true}` |
| `/api/analysis-history` | GET | 이력 배열 |
| `/api/analysis-history?date=YYYY-MM-DD` | GET | 특정일 상세 |
| `/api/logs?name=marcus&lines=100` | GET | 로그 라인 |
| `/api/file?name=xxx.json` | GET | intel 파일 내용 |

## `/api/data` 응답 구조 (output/intel/ 기반)

app.js 줄 90-150 분석 결과:
```javascript
raw.portfolio_summary        // PortfolioSummary
raw.portfolio_summary.total  // { pnl_krw, pnl_pct, total_value_krw, invested_krw }
raw.portfolio_summary.history // Array<{ date, pnl_pct, total_pnl_pct }>
raw.portfolio_summary.holdings // Array<PriceItem>
raw.alerts.alerts            // Array<Alert>
raw.regime                   // RegimeData
raw.supply_data.fear_greed   // FearGreedData
raw.macro                    // Array<MacroItem>
raw.prices                   // Array<PriceItem>
raw.opportunities            // Array<Opportunity>
raw.engine_status            // EngineStatus
raw.marcus_analysis          // string (markdown)
```

## 구현 방향

### web-next/src/types/api.ts
```typescript
export interface PriceItem {
  ticker: string
  name: string
  price: number | null
  prev_close: number | null
  change_pct: number | null
  volume: number | null
  currency: 'KRW' | 'USD'
  market: string
  avg_cost?: number
  pnl_pct?: number | null
}

export interface PortfolioTotal {
  pnl_krw: number
  pnl_pct: number
  total_value_krw: number
  invested_krw: number
  fx_rate?: number
  fx_pnl_krw?: number
}

export interface PortfolioHistory {
  date: string
  pnl_pct: number
  total_pnl_pct?: number
}

export interface PortfolioSummary {
  total: PortfolioTotal
  history: PortfolioHistory[]
  holdings: PriceItem[]
  sectors?: Record<string, number>
}

export interface Alert {
  level: 'critical' | 'warning' | 'info'
  event_type: string
  ticker?: string
  message: string
  value?: number
  threshold?: number
  triggered_at: string
}

export interface MacroItem {
  indicator: string
  value: number
  change_pct: number | null
}

export interface RegimeData {
  regime: string
  confidence: number | null
  vix: number | null
  panic_signal: boolean
  strategy?: {
    stance: string
    cash_ratio: number
  }
}

export interface FearGreedData {
  score: number
  rating: string
}

export interface SupplyData {
  fear_greed?: FearGreedData
}

export interface Opportunity {
  ticker: string
  name: string
  composite_score: number
  discovered_via?: string
  price_at_discovery?: number
}

export interface EngineStatus {
  last_run?: string
  error_count?: number
  db_size_mb?: number
  intel_files?: string[]
}

export interface IntelData {
  portfolio_summary: PortfolioSummary
  alerts: { alerts: Alert[] }
  regime: RegimeData
  supply_data: SupplyData
  macro: MacroItem[]
  prices: PriceItem[]
  opportunities: Opportunity[]
  engine_status: EngineStatus
  marcus_analysis: string
}

export interface ProcessStatus {
  pipeline: { running: boolean; pid?: number }
  marcus: { running: boolean; pid?: number }
}
```

### web-next/src/lib/api.ts
```typescript
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8421'

export async function fetchIntelData(): Promise<IntelData> {
  const res = await fetch(`${BASE}/api/data`)
  if (!res.ok) throw new Error('API 오류')
  return res.json()
}

export async function fetchProcessStatus(): Promise<ProcessStatus> {
  const res = await fetch(`${BASE}/api/status`)
  if (!res.ok) throw new Error('상태 조회 실패')
  return res.json()
}

export async function runPipeline(): Promise<void> {
  await fetch(`${BASE}/api/run-pipeline`, { method: 'POST' })
}

export async function runMarcus(): Promise<void> {
  await fetch(`${BASE}/api/run-marcus`, { method: 'POST' })
}

export async function fetchAnalysisHistory(): Promise<AnalysisHistory[]> {
  const res = await fetch(`${BASE}/api/analysis-history`)
  return res.json()
}

export async function fetchAnalysisDetail(date: string): Promise<AnalysisDetail> {
  const res = await fetch(`${BASE}/api/analysis-history?date=${date}`)
  return res.json()
}

export async function fetchLogs(name: string, lines = 100): Promise<{ lines: string[] }> {
  const res = await fetch(`${BASE}/api/logs?name=${name}&lines=${lines}`)
  return res.json()
}
```

### web-next/src/hooks/useIntelData.ts
```typescript
import useSWR from 'swr'
import { fetchIntelData } from '@/lib/api'

export function useIntelData() {
  const { data, error, isLoading, mutate } = useSWR('intel-data', fetchIntelData, {
    refreshInterval: 30_000,
    revalidateOnFocus: false,
  })
  return { data, error, isLoading, mutate }
}
```

### web-next/src/hooks/useProcessStatus.ts
```typescript
import useSWR from 'swr'
import { fetchProcessStatus } from '@/lib/api'

export function useProcessStatus() {
  const { data, mutate } = useSWR('process-status', fetchProcessStatus, {
    refreshInterval: 5_000,
    revalidateOnFocus: false,
  })
  return {
    pipelineRunning: data?.pipeline?.running ?? false,
    marcusRunning: data?.marcus?.running ?? false,
    mutate,
  }
}
```

## 검증
```bash
cd web-next && npx tsc --noEmit
grep -r ": any" src/types/ src/lib/ src/hooks/ | wc -l  # → 0
```
