export interface PriceItem {
  ticker: string
  name: string
  price: number
  prev_close?: number
  change_pct: number
  volume?: number
  market?: string
  avg_price?: number
  quantity?: number
  value_krw?: number
  pnl_krw?: number
  pnl_pct?: number
  currency?: string
}

export interface MacroItem {
  indicator: string
  value: number
  change_pct?: number
  label?: string
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
  total_pnl_pct?: number
  pnl_pct?: number
  total_pnl_krw?: number
}

export interface PortfolioSummary {
  total?: {
    invested_krw?: number
    total_value_krw?: number
    pnl_krw?: number
    pnl_pct?: number
    fx_pnl_krw?: number
  }
  holdings?: PriceItem[]
  history?: PortfolioHistory[]
}

export interface RegimeData {
  regime?: string
  confidence?: number
  vix?: number
  cash_ratio?: number
  description?: string
}

export interface SupplyData {
  fear_greed_index?: number
  fear_greed_label?: string
  foreign_net?: number
  institution_net?: number
}

export interface Opportunity {
  ticker: string
  name?: string
  composite_score?: number
  keywords?: string[]
  reason?: string
}

export interface EngineStatus {
  last_run?: string
  error_count?: number
  db_size_mb?: number
  intel_files?: string[]
}

export interface IntelData {
  portfolio_summary?: PortfolioSummary
  prices?: PriceItem[]
  macro?: MacroItem[]
  alerts?: {
    alerts?: Alert[]
    count?: number
  }
  market_regime?: RegimeData
  supply_data?: SupplyData
  opportunities?: Opportunity[]
  marcus_analysis?: string
  engine_status?: EngineStatus
  last_updated?: string
}

export interface ProcessStatus {
  pipeline_running?: boolean
  marcus_running?: boolean
  last_run?: string
  next_run?: string
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
