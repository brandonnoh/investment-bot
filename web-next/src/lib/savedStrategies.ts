export interface SavedStrategy {
  id: string
  savedAt: string
  capital: number
  leverageAmt: number
  riskLevel: number
  recommendation: string
}

const KEY = 'mc-saved-strategies'

export function loadStrategies(): SavedStrategy[] {
  if (typeof window === 'undefined') return []
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]')
  } catch {
    return []
  }
}

export function saveStrategy(strategy: Omit<SavedStrategy, 'id' | 'savedAt'>): SavedStrategy {
  const entry: SavedStrategy = {
    ...strategy,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    savedAt: new Date().toISOString(),
  }
  const list = loadStrategies()
  list.unshift(entry)
  localStorage.setItem(KEY, JSON.stringify(list))
  return entry
}

export function deleteStrategy(id: string): void {
  const list = loadStrategies().filter(s => s.id !== id)
  localStorage.setItem(KEY, JSON.stringify(list))
}

export function fmtAmt(v: number): string {
  return v >= 100_000_000
    ? `${(v / 100_000_000).toFixed(1)}억`
    : `${(v / 10_000).toLocaleString()}만`
}

const RISK_LABELS: Record<number, string> = {
  1: '보수', 2: '보수-중립', 3: '중립', 4: '공격', 5: '초공격',
}
export function riskLabel(level: number): string {
  return RISK_LABELS[level] ?? `Lv.${level}`
}
