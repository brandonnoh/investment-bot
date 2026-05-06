import useSWR from 'swr'

export interface ExtraAsset {
  id: number
  name: string
  type: string
  asset_type?: string
  current_value_krw: number
  monthly_deposit_krw: number
  is_fixed: boolean
  maturity_date: string | null
  note: string | null
}

export interface WealthHistoryEntry {
  date: string
  total_wealth_krw: number
  investment_value_krw: number
  extra_assets_krw: number
}

export interface WealthSummary {
  total_wealth_krw: number
  investment_krw: number
  investment_pnl_krw: number
  investment_pnl_pct: number
  extra_assets_krw: number
  monthly_recurring_krw: number
  extra_assets: ExtraAsset[]
  wealth_history: WealthHistoryEntry[]
  last_updated: string | null
}

const fetcher = (url: string) =>
  fetch(url).then(r => r.json()).then(d => {
    if (d && d.error) throw new Error(d.error)
    return d
  })

export function useWealthData() {
  const { data, error, mutate } = useSWR<WealthSummary>('/api/wealth', fetcher, {
    refreshInterval: 60000,
  })
  return { data, isLoading: !data && !error, mutate }
}
