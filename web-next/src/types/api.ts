// 실제 Flask API 응답 구조에 맞춘 타입 정의

export interface PriceItem {
  ticker: string
  name: string
  price: number
  prev_close?: number
  change_pct: number
  volume?: number
  market?: string
  sector?: string
  currency?: string
  // 보유종목 전용 필드 (실제 API: avg_cost, qty, current_value_krw)
  avg_cost?: number
  qty?: number
  current_value_krw?: number
  invested_krw?: number
  pnl_krw?: number
  pnl_pct?: number
  stock_pnl_krw?: number
  fx_pnl_krw?: number
  timestamp?: string
}

export interface MacroItem {
  indicator: string
  ticker?: string
  value: number
  change_pct?: number
  category?: string
  label?: string
}

export interface MacroData {
  updated_at?: string
  count?: number
  indicators: MacroItem[]
}

export interface Alert {
  level: 'critical' | 'warning' | 'info'
  event_type?: string
  ticker?: string
  message: string
  value?: number
  threshold?: number
  triggered_at?: string
}

export interface PortfolioHistory {
  date: string
  total_value_krw?: number
  total_invested_krw?: number
  total_pnl_krw?: number
  total_pnl_pct?: number
  fx_rate?: number
}

export interface PortfolioSummary {
  updated_at?: string
  exchange_rate?: number
  total?: {
    invested_krw?: number
    current_value_krw?: number   // 실제 필드명
    pnl_krw?: number
    pnl_pct?: number
    stock_pnl_krw?: number
    fx_pnl_krw?: number
  }
  holdings?: PriceItem[]
  sectors?: Array<{ sector: string; weight_pct: number; value_krw: number; pnl_pct: number; stocks: string[] }>
  history?: PortfolioHistory[]
}

export interface RegimeStrategy {
  stance?: string
  preferred_sectors?: string[]
  avoid_sectors?: string[]
  cash_ratio?: number
}

export interface RegimeData {
  classified_at?: string
  regime?: string
  confidence?: number
  vix?: number
  fx_change?: number
  oil_change?: number
  panic_signal?: boolean
  strategy?: RegimeStrategy
}

export interface FearGreed {
  score?: number
  rating?: string
  previous_close?: number | null
}

export interface SupplyData {
  updated_at?: string
  fear_greed?: FearGreed        // 실제: supply_data.fear_greed.score
  krx_supply?: Record<string, unknown>
}

export interface Opportunity {
  ticker: string
  name?: string
  composite_score?: number
  discovered_via?: string
  source?: string
  // 실제 value_screener 출력 필드
  sector?: string
  screen_reason?: string
  grade?: string
  factors?: Record<string, number>
  rsi?: number
  per?: number
  pbr?: number
  roe?: number
  pos_52w?: number
  // 레거시 필드 (하위 호환)
  url?: string
  sentiment?: number
  title?: string
  keywords?: string[]
}

export interface OpportunitiesData {
  updated_at?: string
  keywords?: string[]
  opportunities: Opportunity[]  // 실제: data.opportunities.opportunities[]
  total_count?: number
  summary?: string
}

export interface EngineStatus {
  updated_at?: string
  pipeline_ok?: boolean
  total_errors?: number
  db_size_mb?: number
  uptime_days?: number
  first_run?: string
  modules?: Record<string, unknown>
}

export interface IntelData {
  portfolio_summary?: PortfolioSummary
  prices?: { prices?: PriceItem[] }
  macro?: MacroData                    // 실제: { indicators: MacroItem[] }
  alerts?: {
    alerts?: Alert[]
    count?: number
  }
  regime?: RegimeData                  // 실제 키: regime (market_regime 아님)
  supply_data?: SupplyData
  opportunities?: OpportunitiesData    // 실제: { opportunities: [...] }
  price_analysis?: Record<string, unknown>
  screener_results?: Record<string, unknown>
  news?: Record<string, unknown>
  fundamentals?: Record<string, unknown>
  holdings_proposal?: Record<string, unknown>
  performance_report?: Record<string, unknown>
  simulation_report?: Record<string, unknown>
  marcus_analysis?: string
  engine_status?: EngineStatus
  last_updated?: string
}

export interface ProcessStatus {
  pipeline?: { running?: boolean }
  marcus?: { running?: boolean }
}

export interface AnalysisHistory {
  date: string
  confidence_level?: number
  stance?: string
  today_call?: string
}

export interface AnalysisDetail {
  date: string
  analysis: string
}

export interface LogResponse {
  lines: string[]
}
