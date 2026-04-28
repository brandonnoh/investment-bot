'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'
import { fgStyle } from '@/hooks/useCountUp'

const GOLD_TICKER = 'GOLD_KRW_G'

export function MobileHero({ excludeGold, onToggle }: { excludeGold: boolean; onToggle: () => void }) {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const holdings = data?.portfolio_summary?.holdings ?? []

  const pnlPct: number = (() => {
    if (!excludeGold) return total?.pnl_pct ?? 0
    const f = holdings.filter(h => h.ticker !== GOLD_TICKER)
    const inv = f.reduce((s, h) => s + (h.invested_krw ?? 0), 0)
    const cur = f.reduce((s, h) => s + (h.current_value_krw ?? 0), 0)
    return inv > 0 ? ((cur - inv) / inv) * 100 : 0
  })()

  const pnlKrw: number = (() => {
    if (!excludeGold) return total?.pnl_krw ?? 0
    const f = holdings.filter(h => h.ticker !== GOLD_TICKER)
    const inv = f.reduce((s, h) => s + (h.invested_krw ?? 0), 0)
    const cur = f.reduce((s, h) => s + (h.current_value_krw ?? 0), 0)
    return cur - inv
  })()

  const currentKrw: number = (() => {
    if (!excludeGold) return total?.current_value_krw ?? 0
    return holdings
      .filter(h => h.ticker !== GOLD_TICKER)
      .reduce((s, h) => s + (h.current_value_krw ?? 0), 0)
  })()

  const investedKrw: number | undefined = (() => {
    if (!excludeGold) return total?.invested_krw
    return holdings
      .filter(h => h.ticker !== GOLD_TICKER)
      .reduce((s, h) => s + (h.invested_krw ?? 0), 0)
  })()

  const isNeg = pnlPct < 0
  const color = pctColor(pnlPct)

  return (
    <div className="border border-mc-border bg-mc-card rounded-lg px-5 py-5">
      <div className="flex items-center gap-2 mb-3">
        <div className="text-[10px] text-muted-foreground font-mono tracking-widest uppercase">Portfolio P&amp;L</div>
        <button
          onClick={onToggle}
          className={`text-[11px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
            excludeGold
              ? 'bg-gold/10 text-gold border-gold/30'
              : 'text-muted-foreground border-mc-border hover:border-gold/30 hover:text-gold'
          }`}
        >
          {excludeGold ? '금 제외 ✓' : '금 포함'}
        </button>
      </div>
      <div className={`text-5xl font-mono font-bold tabular-nums leading-none ${color}`}>
        {isNeg ? '' : '+'}{pnlPct.toFixed(2)}%
      </div>
      <div className={`text-base font-mono mt-2 tabular-nums ${color}`}>
        {isNeg ? '' : '+'}₩{Math.round(pnlKrw).toLocaleString()}
      </div>
      <div className="mt-4 space-y-0.5">
        <div className="text-xs text-muted-foreground font-mono tabular-nums">
          평가금액 ₩{Math.round(currentKrw).toLocaleString()}
        </div>
        <div className="text-xs text-muted-foreground font-mono">
          투자원금 {fmtKrw(investedKrw)}원
        </div>
      </div>
    </div>
  )
}

export function MobileMarketBar() {
  const { data } = useIntelData()
  const regime = data?.regime
  const supply = data?.supply_data
  const fg = supply?.fear_greed?.score
  const cashRatio = regime?.strategy?.cash_ratio
  const { color: fgColor } = fgStyle(fg)

  return (
    <div className="border border-mc-border bg-mc-card rounded-lg px-4 py-2.5 flex items-center overflow-x-auto gap-0">
      <span className="text-gold text-xs font-mono font-bold whitespace-nowrap">{regime?.regime ?? '—'}</span>
      {regime?.confidence && <>
        <span className="text-mc-border mx-2 text-xs">·</span>
        <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">신뢰 {(regime.confidence * 100).toFixed(0)}%</span>
      </>}
      {fg !== undefined && <>
        <span className="text-mc-border mx-2 text-xs">·</span>
        <span className={`text-xs font-mono whitespace-nowrap ${fgColor}`}>Fear {fg}</span>
      </>}
      {regime?.vix !== undefined && <>
        <span className="text-mc-border mx-2 text-xs">·</span>
        <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">VIX {regime.vix.toFixed(1)}</span>
      </>}
      {cashRatio != null && <>
        <span className="text-mc-border mx-2 text-xs">·</span>
        <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">현금 {(cashRatio * 100).toFixed(0)}%</span>
      </>}
    </div>
  )
}

export function MobileHoldingsList() {
  const { data, isLoading } = useIntelData()
  const holdings = data?.portfolio_summary?.holdings ?? []

  if (isLoading) return <div className="text-muted-foreground text-xs p-4 font-mono">로딩 중...</div>

  return (
    <div className="border border-mc-border bg-mc-card rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-mc-border">
        <span className="text-[10px] font-mono text-muted-foreground tracking-widest uppercase">Holdings</span>
      </div>
      {holdings.length === 0 ? (
        <div className="text-center text-muted-foreground text-xs py-8 font-mono">보유 종목 없음</div>
      ) : (
        <div className="divide-y divide-mc-border">
          {holdings.map(h => (
            <div key={h.ticker} className="flex items-center justify-between px-4 py-3.5">
              <div>
                <div className="text-sm font-medium">{h.name}</div>
                <div className="text-[10px] text-muted-foreground font-mono">{h.ticker}</div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-mono font-bold tabular-nums ${pctColor(h.pnl_pct)}`}>
                  {fmtPct(h.pnl_pct)}
                </div>
                <div className="text-[10px] text-muted-foreground font-mono tabular-nums">
                  {h.price?.toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
