const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

export interface SavedStrategy {
  id: number
  saved_at: string
  capital: number
  leverage_amt: number
  risk_level: number
  recommendation: string
  loans_json?: string      // JSON array: [{type,amount,rate,...}]
  monthly_savings?: number
}

export interface SavedLoan {
  type: 'minus' | 'credit'
  amount: number
  rate: number
  grace_period?: number
  repay_period?: number
}

export function parseLoans(loansJson: string | undefined): SavedLoan[] {
  if (!loansJson) return []
  try { return JSON.parse(loansJson) as SavedLoan[] } catch { return [] }
}

export async function loadStrategies(limit = 20): Promise<SavedStrategy[]> {
  try {
    const res = await fetch(`${BASE}/api/advisor-strategies?limit=${limit}`)
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export async function saveStrategy(
  capital: number,
  leverage_amt: number,
  risk_level: number,
  recommendation: string,
  loans: SavedLoan[] = [],
  monthly_savings = 0,
): Promise<number | null> {
  try {
    const res = await fetch(`${BASE}/api/advisor-strategies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capital, leverage_amt, risk_level, recommendation, loans, monthly_savings }),
    })
    if (!res.ok) return null
    const data = await res.json()
    return data.id ?? null
  } catch {
    return null
  }
}

export async function deleteStrategy(id: number): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/advisor-strategies/${id}`, { method: 'DELETE' })
    return res.ok
  } catch {
    return false
  }
}

export { fmtAmt } from '@/lib/format'

const RISK_LABELS: Record<number, string> = {
  1: '보수', 2: '보수-중립', 3: '중립', 4: '공격', 5: '초공격',
}
export function riskLabel(level: number): string {
  return RISK_LABELS[level] ?? `Lv.${level}`
}
