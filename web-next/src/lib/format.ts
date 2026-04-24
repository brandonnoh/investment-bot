/** 금액을 억/만 단위로 포맷 (예: 1.5억, 3,500만) */
export function fmtAmt(v: number): string {
  return v >= 100_000_000
    ? `${(v / 100_000_000).toFixed(1)}억`
    : `${(v / 10_000).toLocaleString()}만`
}

/** 금액을 천단위 콤마 형식으로 포맷 (예: 47,312,450) */
export function fmtKrw(v?: number): string {
  if (v === undefined || v === null) return '—'
  return Math.round(v).toLocaleString('ko-KR')
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
