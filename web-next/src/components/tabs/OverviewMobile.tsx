'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'
import { fgStyle } from '@/hooks/useCountUp'

export function MobileHero() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const pnlPct = total?.pnl_pct ?? 0
  const isNeg = pnlPct < 0
  const color = pctColor(pnlPct)

  return (
    <div className="border border-mc-border bg-mc-card rounded-lg px-5 py-5">
      <div className="text-[10px] text-muted-foreground font-mono tracking-widest uppercase mb-3">Portfolio P&amp;L</div>
      <div className={`text-5xl font-mono font-bold tabular-nums leading-none ${color}`}>
        {isNeg ? '' : '+'}{pnlPct?.toFixed(2)}%
      </div>
      <div className={`text-base font-mono mt-2 tabular-nums ${color}`}>
        {isNeg ? '' : '+'}₩{total?.pnl_krw?.toLocaleString()}
      </div>
      <div className="text-xs text-muted-foreground font-mono mt-4 tabular-nums">
        평가금액 ₩{total?.current_value_krw?.toLocaleString()}
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
