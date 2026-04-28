'use client'

import { useState } from 'react'
import { useIntelData } from '@/hooks/useIntelData'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'
import { SyncBadge } from '@/components/SyncBadge'
import { useCountUp, fgStyle } from '@/hooks/useCountUp'
import { MobileHero, MobileMarketBar, MobileHoldingsList } from '@/components/tabs/OverviewMobile'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'

const GOLD_TICKER = 'GOLD_KRW_G'

// ── 데스크탑 War Room: 좌측 포트폴리오 패널 ─────────────────

function PortfolioPanel({ excludeGold, onToggleGold }: { excludeGold: boolean; onToggleGold: () => void }) {
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

  const aPct = useCountUp(pnlPct)
  const aKrw = useCountUp(pnlKrw)
  const aCurrent = useCountUp(currentKrw)

  const isNeg = pnlPct < 0
  const color = pctColor(pnlPct)

  return (
    <div className="flex flex-col justify-center py-8 px-8 border-r border-mc-border">
      <div className="flex items-center gap-2 mb-4">
        <div className="text-[10px] text-muted-foreground font-mono tracking-widest uppercase">
          Portfolio P&amp;L
        </div>
        <button
          onClick={onToggleGold}
          className={`text-[11px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
            excludeGold
              ? 'bg-gold/10 text-gold border-gold/30'
              : 'text-muted-foreground border-mc-border hover:border-gold/30 hover:text-gold'
          }`}
        >
          {excludeGold ? '금 제외 ✓' : '금 포함'}
        </button>
      </div>
      <div
        className={`font-mono font-bold leading-none tabular-nums ${color}`}
        style={{ fontSize: 'clamp(3.5rem, 5.5vw, 5.5rem)' }}
      >
        {isNeg ? '' : '+'}{aPct.toFixed(2)}%
      </div>
      <div className={`font-mono text-xl mt-3 tabular-nums ${color}`}>
        {isNeg ? '' : '+'}₩{Math.round(aKrw).toLocaleString()}
      </div>
      <div className="mt-5 space-y-1">
        <div className="text-xs text-muted-foreground font-mono tabular-nums">
          평가금액 ₩{Math.round(aCurrent).toLocaleString()}
        </div>
        <div className="text-xs text-muted-foreground font-mono">
          투자원금 {fmtKrw(investedKrw)}원
        </div>
      </div>
    </div>
  )
}

// ── 데스크탑 War Room: 우측 마켓 패널 (카드 없음) ───────────

function MarketPanel() {
  const { data } = useIntelData()
  const regime = data?.regime
  const supply = data?.supply_data
  const macro = data?.macro?.indicators ?? []

  const fg = supply?.fear_greed?.score
  const fgLabel = supply?.fear_greed?.rating
  const cashRatio = regime?.strategy?.cash_ratio
  const { color: fgColor, bar: fgBar, pulse: fgPulse } = fgStyle(fg)

  return (
    <div className="flex flex-col py-8 px-7">
      <div className="text-[10px] text-muted-foreground font-mono tracking-widest uppercase mb-3">Market Regime</div>
      <div className="text-gold font-mono font-bold text-2xl tracking-wide mb-2">{regime?.regime ?? '—'}</div>
      <div className="flex gap-5 mb-6">
        {[
          ['신뢰도', regime?.confidence ? `${(regime.confidence * 100).toFixed(0)}%` : '—'],
          ['VIX', regime?.vix?.toFixed(1) ?? '—'],
          ['현금', cashRatio != null ? `${(cashRatio * 100).toFixed(0)}%` : '—'],
        ].map(([k, v]) => (
          <div key={k} className="text-xs font-mono text-muted-foreground">
            {k} <span className="text-foreground">{v}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-mc-border mb-5" />

      {fg !== undefined && (
        <div className="mb-6">
          <div className="text-[10px] text-muted-foreground font-mono tracking-widest uppercase mb-3">Fear &amp; Greed</div>
          <div className="flex items-baseline gap-3 mb-2">
            <span className={`font-mono font-bold text-4xl tabular-nums ${fgColor} ${fgPulse ? 'animate-pulse' : ''}`}>
              {fg}
            </span>
            <span className={`text-xs font-mono uppercase tracking-wider ${fgColor}`}>{fgLabel}</span>
          </div>
          <div className="h-px bg-mc-border rounded-full overflow-hidden">
            <div className={`h-full ${fgBar} transition-all duration-1000`} style={{ width: `${fg}%` }} />
          </div>
        </div>
      )}

      {macro.length > 0 && (
        <>
          <div className="border-t border-mc-border mb-4" />
          <div className="space-y-2">
            {macro.slice(0, 4).map((m) => (
              <div key={m.indicator} className="flex justify-between items-baseline">
                <span className="text-[11px] text-muted-foreground font-mono">{m.indicator}</span>
                <span className={`text-[11px] font-mono tabular-nums ${pctColor(m.change_pct)}`}>
                  {m.value?.toFixed(2)}
                  {m.change_pct !== undefined && <span className="opacity-60 ml-1">{fmtPct(m.change_pct)}</span>}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── 보유 종목 테이블 ─────────────────────────────────────────

function HoldingsTable() {
  const { data, isLoading } = useIntelData()
  const holdings = data?.portfolio_summary?.holdings ?? []
  const priceTs = data?.prices?.prices?.[0]?.timestamp

  if (isLoading) return (
    <div className="border border-mc-border bg-mc-card rounded-lg p-4 text-muted-foreground text-xs font-mono">
      데이터 로딩 중...
    </div>
  )

  return (
    <div className="border border-mc-border bg-mc-card rounded-lg overflow-hidden">
      <div className="px-5 py-3 border-b border-mc-border flex items-center gap-2">
        <span className="text-[10px] font-mono text-muted-foreground tracking-widest uppercase">Holdings</span>
        <SyncBadge timestamp={priceTs} />
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-mc-border hover:bg-transparent">
              {['종목명', '현재가', '등락', '평균단가', '평가손익', '통화'].map((h, i) => (
                <TableHead key={h}
                  className={`text-[10px] text-muted-foreground font-mono tracking-wider uppercase py-2
                    ${i > 0 ? 'text-right' : ''}
                    ${i === 3 || i === 5 ? 'hidden sm:table-cell' : ''}`}
                >
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {holdings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground text-xs py-10 font-mono">
                  보유 종목 없음
                </TableCell>
              </TableRow>
            ) : holdings.map((h) => (
              <TableRow key={h.ticker} className="border-mc-border">
                <TableCell className="py-3.5">
                  <div className="text-sm font-medium">{h.name}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">{h.ticker}</div>
                </TableCell>
                <TableCell className="text-xs text-right font-mono tabular-nums">{h.price?.toLocaleString()}</TableCell>
                <TableCell className={`text-xs text-right font-mono tabular-nums ${pctColor(h.change_pct)}`}>
                  {fmtPct(h.change_pct)}
                </TableCell>
                <TableCell className="text-xs text-right font-mono tabular-nums hidden sm:table-cell text-muted-foreground">
                  {h.avg_cost?.toLocaleString() ?? '—'}
                </TableCell>
                <TableCell className={`text-xs text-right font-mono tabular-nums ${pctColor(h.pnl_pct)}`}>
                  <div>{fmtPct(h.pnl_pct)}</div>
                  {h.pnl_krw !== undefined && (
                    <div className="text-[10px] text-muted-foreground">{fmtKrw(h.pnl_krw)}원</div>
                  )}
                </TableCell>
                <TableCell className="text-xs text-right text-muted-foreground font-mono hidden sm:table-cell">
                  {h.currency ?? '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

// ── 메인 ────────────────────────────────────────────────────

export function OverviewTab() {
  const [excludeGold, setExcludeGold] = useState(false)
  const toggleGold = () => setExcludeGold(e => !e)

  return (
    <div className="space-y-3">
      <div className="lg:hidden space-y-3">
        <MobileHero excludeGold={excludeGold} onToggle={toggleGold} />
        <MobileMarketBar />
        <MobileHoldingsList />
      </div>
      <div className="hidden lg:block space-y-4">
        <div className="grid grid-cols-[3fr_2fr] border border-mc-border bg-mc-card rounded-lg overflow-hidden">
          <PortfolioPanel excludeGold={excludeGold} onToggleGold={toggleGold} />
          <MarketPanel />
        </div>
        <HoldingsTable />
      </div>
    </div>
  )
}
