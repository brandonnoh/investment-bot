'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'
import { SyncBadge } from '@/components/SyncBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function StatsStrip() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const regime = data?.regime                          // 실제 키: regime
  const alertCount = data?.alerts?.count ?? data?.alerts?.alerts?.length ?? 0

  const stats = [
    {
      label: '포트폴리오 손익',
      value: fmtPct(total?.pnl_pct),
      sub: fmtKrw(total?.pnl_krw) + '원',
      color: pctColor(total?.pnl_pct),
    },
    {
      label: '평가금액',
      value: fmtKrw(total?.current_value_krw) + '원',  // 실제 필드: current_value_krw
      sub: `투자원금 ${fmtKrw(total?.invested_krw)}원`,
      color: 'text-foreground',
    },
    {
      label: '시장 국면',
      value: regime?.regime ?? '—',
      sub: regime?.confidence ? `신뢰도 ${(regime.confidence * 100).toFixed(0)}%` : '—',
      color: 'text-gold',
    },
    {
      label: '활성 알림',
      value: alertCount.toString(),
      sub: alertCount > 0 ? '확인 필요' : '이상 없음',
      color: alertCount > 0 ? 'text-mc-red' : 'text-mc-green',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">  {/* 모바일 2열, 데스크탑 4열 */}
      {stats.map((s) => (
        <Card key={s.label} className="bg-mc-card border-mc-border">
          <CardContent className="pt-3 pb-3">
            <div className="text-xs text-muted-foreground">{s.label}</div>
            <div className={`text-lg font-mono font-bold mt-0.5 ${s.color}`}>{s.value}</div>
            <div className="text-xs text-muted-foreground">{s.sub}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function HoldingsTable() {
  const { data, isLoading } = useIntelData()
  const holdings = data?.portfolio_summary?.holdings ?? []
  const priceTs = data?.prices?.prices?.[0]?.timestamp

  if (isLoading) return <div className="text-muted-foreground text-xs p-4">로딩 중...</div>

  return (
    <Card className="bg-mc-card border-mc-border">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-xs font-mono">
          보유 종목<SyncBadge timestamp={priceTs} />
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-mc-border hover:bg-transparent">
              <TableHead className="text-xs text-muted-foreground">종목명</TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">현재가</TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">등락</TableHead>
              <TableHead className="text-xs text-muted-foreground text-right hidden sm:table-cell">평균단가</TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">평가손익</TableHead>
              <TableHead className="text-xs text-muted-foreground text-right hidden sm:table-cell">통화</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {holdings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground text-xs py-6">
                  보유 종목 없음
                </TableCell>
              </TableRow>
            ) : (
              holdings.map((h) => (
                <TableRow key={h.ticker} className="border-mc-border min-h-[44px]">
                  <TableCell className="text-xs">
                    <div className="font-medium">{h.name}</div>
                    <div className="text-muted-foreground font-mono">{h.ticker}</div>
                  </TableCell>
                  <TableCell className="text-xs text-right font-mono">
                    {h.price?.toLocaleString()}
                  </TableCell>
                  <TableCell className={`text-xs text-right font-mono ${pctColor(h.change_pct)}`}>
                    {fmtPct(h.change_pct)}
                  </TableCell>
                  <TableCell className="text-xs text-right font-mono hidden sm:table-cell">
                    {h.avg_cost?.toLocaleString() ?? '—'}  {/* 실제 필드: avg_cost */}
                  </TableCell>
                  <TableCell className={`text-xs text-right font-mono ${pctColor(h.pnl_pct)}`}>
                    {fmtPct(h.pnl_pct)}
                    {h.pnl_krw !== undefined && (
                      <div className="text-muted-foreground">{fmtKrw(h.pnl_krw)}원</div>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-right text-muted-foreground hidden sm:table-cell">
                    {h.currency ?? '—'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function MarketSidebar() {
  const { data } = useIntelData()
  const regime = data?.regime                            // 실제 키: regime
  const supply = data?.supply_data
  const macro = data?.macro?.indicators ?? []            // 실제: macro.indicators[]

  const fg = supply?.fear_greed?.score                  // 실제: supply_data.fear_greed.score
  const fgLabel = supply?.fear_greed?.rating            // 실제: supply_data.fear_greed.rating
  const cashRatio = regime?.strategy?.cash_ratio        // 실제: regime.strategy.cash_ratio

  const fgColor = fg !== undefined
    ? fg <= 25 ? 'text-mc-red'
    : fg <= 45 ? 'text-amber'
    : fg <= 75 ? 'text-mc-green'
    : 'text-mc-green'
    : 'text-muted-foreground'

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
      <Card className="bg-mc-card border-mc-border min-w-[180px] shrink-0 lg:min-w-0 lg:shrink">
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-xs font-mono">시장 국면</CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3 space-y-1.5">
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">국면</span>
            <span className="text-xs text-gold font-mono">{regime?.regime ?? '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">신뢰도</span>
            <span className="text-xs font-mono">
              {regime?.confidence ? `${(regime.confidence * 100).toFixed(0)}%` : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">VIX</span>
            <span className="text-xs font-mono">{regime?.vix?.toFixed(1) ?? '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">현금비중</span>
            <span className="text-xs font-mono">
              {cashRatio != null ? `${(cashRatio * 100).toFixed(0)}%` : '—'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-mc-card border-mc-border min-w-[180px] shrink-0 lg:min-w-0 lg:shrink">
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-xs font-mono">Fear & Greed</CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3">
          <div className={`text-2xl font-mono font-bold ${fgColor}`}>{fg ?? '—'}</div>
          <div className="text-xs text-muted-foreground mb-2">{fgLabel ?? ''}</div>
          {fg !== undefined && <Progress value={fg} className="h-1.5" />}
        </CardContent>
      </Card>

      {macro.length > 0 && (
        <Card className="bg-mc-card border-mc-border min-w-[180px] shrink-0 lg:min-w-0 lg:shrink">
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-xs font-mono">매크로</CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3 space-y-1.5">
            {macro.slice(0, 4).map((m) => (
              <div key={m.indicator} className="flex justify-between">
                <span className="text-xs text-muted-foreground">{m.indicator}</span>
                <span className={`text-xs font-mono ${pctColor(m.change_pct)}`}>
                  {m.value?.toFixed(2)}
                  {m.change_pct !== undefined && ` (${fmtPct(m.change_pct)})`}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function PortfolioHero() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total

  return (
    <Card className="bg-mc-card border-mc-border">
      <CardContent className="pt-5 pb-5 px-5">
        <div className="text-xs text-muted-foreground font-mono">포트폴리오 평가금액</div>
        <div className="text-4xl font-mono font-bold mt-2 text-foreground">
          {fmtKrw(total?.current_value_krw)}<span className="text-2xl text-muted-foreground ml-1">원</span>
        </div>
        <div className={`flex items-center gap-3 mt-2 ${pctColor(total?.pnl_pct)}`}>
          <span className="text-2xl font-mono font-bold">{fmtPct(total?.pnl_pct)}</span>
          <span className="text-base font-mono">{fmtKrw(total?.pnl_krw)}원</span>
        </div>
        <div className="text-xs text-muted-foreground font-mono mt-2">
          투자원금 {fmtKrw(total?.invested_krw)}원
        </div>
      </CardContent>
    </Card>
  )
}

function MarketBar() {
  const { data } = useIntelData()
  const regime = data?.regime
  const supply = data?.supply_data
  const fg = supply?.fear_greed?.score
  const cashRatio = regime?.strategy?.cash_ratio

  const fgColor = fg !== undefined
    ? fg <= 25 ? 'text-mc-red'
    : fg <= 45 ? 'text-amber'
    : 'text-mc-green'
    : 'text-muted-foreground'

  return (
    <div className="bg-mc-card border border-mc-border rounded-lg px-4 py-2.5 flex items-center gap-0 overflow-x-auto">
      <span className="text-gold text-xs font-mono font-bold whitespace-nowrap">{regime?.regime ?? '—'}</span>
      {regime?.confidence && (
        <>
          <span className="text-mc-border mx-2 text-xs">·</span>
          <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">신뢰 {(regime.confidence * 100).toFixed(0)}%</span>
        </>
      )}
      {fg !== undefined && (
        <>
          <span className="text-mc-border mx-2 text-xs">·</span>
          <span className={`text-xs font-mono whitespace-nowrap ${fgColor}`}>Fear {fg}</span>
        </>
      )}
      {regime?.vix !== undefined && (
        <>
          <span className="text-mc-border mx-2 text-xs">·</span>
          <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">VIX {regime.vix.toFixed(1)}</span>
        </>
      )}
      {cashRatio != null && (
        <>
          <span className="text-mc-border mx-2 text-xs">·</span>
          <span className="text-muted-foreground text-xs font-mono whitespace-nowrap">현금 {(cashRatio * 100).toFixed(0)}%</span>
        </>
      )}
    </div>
  )
}

function MobileHoldingsList() {
  const { data, isLoading } = useIntelData()
  const holdings = data?.portfolio_summary?.holdings ?? []

  if (isLoading) return <div className="text-muted-foreground text-xs p-4">로딩 중...</div>

  return (
    <Card className="bg-mc-card border-mc-border">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-xs font-mono">보유 종목</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-2">
        {holdings.length === 0 ? (
          <div className="text-center text-muted-foreground text-xs py-6">보유 종목 없음</div>
        ) : (
          <div className="divide-y divide-mc-border">
            {holdings.map(h => (
              <div key={h.ticker} className="flex items-center justify-between py-3.5 min-h-[56px]">
                <div>
                  <div className="text-sm font-medium">{h.name}</div>
                  <div className="text-xs text-muted-foreground font-mono">{h.ticker}</div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-mono font-bold ${pctColor(h.pnl_pct)}`}>
                    {fmtPct(h.pnl_pct)}
                  </div>
                  <div className="text-xs text-muted-foreground font-mono">
                    {h.price?.toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function OverviewTab() {
  return (
    <div className="space-y-3">
      {/* 모바일 전용 레이아웃 (lg 미만) */}
      <div className="lg:hidden space-y-3">
        <PortfolioHero />
        <MarketBar />
        <MobileHoldingsList />
      </div>

      {/* 데스크탑 전용 레이아웃 (lg 이상) */}
      <div className="hidden lg:block space-y-4">
        <StatsStrip />
        <div className="grid grid-cols-[1fr_260px] gap-4">
          <div className="space-y-4">
            <HoldingsTable />
          </div>
          <div>
            <MarketSidebar />
          </div>
        </div>
      </div>
    </div>
  )
}
