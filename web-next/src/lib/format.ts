/** 금액을 축약 형식으로 포맷 (예: 1.2M, 350K) */
export function fmtKrw(v?: number): string {
  if (v === undefined || v === null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`
  return v.toFixed(0)
}

/** 퍼센트를 부호 포함 형식으로 포맷 (예: +1.23%) */
export function fmtPct(v?: number): string {
  if (v === undefined || v === null) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

/** 퍼센트 값에 따른 색상 클래스 반환 */
export function pctColor(v?: number): string {
  if (v === undefined || v === null) return 'text-muted-foreground'
  if (v > 0) return 'text-mc-green'
  if (v < 0) return 'text-mc-red'
  return 'text-muted-foreground'
}
