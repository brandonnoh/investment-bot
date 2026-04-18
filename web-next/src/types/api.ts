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
  sectors?: Record<string, number>
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
  last_run?: string
  error_count?: number
  db_size_mb?: number
  intel_files?: string[]
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
