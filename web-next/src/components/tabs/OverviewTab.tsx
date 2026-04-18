'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'
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

/** 상단 4개 요약 카드 */
function StatsStrip() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const regime = data?.market_regime
  const alertCount =
    data?.alerts?.count ?? data?.alerts?.alerts?.length ?? 0

  const stats = [
    {
      label: '포트폴리오 손익',
      value: fmtPct(total?.pnl_pct),
      sub: fmtKrw(total?.pnl_krw) + '원',
      color: pctColor(total?.pnl_pct),
    },
    {
      label: '평가금액',
      value: fmtKrw(total?.total_value_krw) + '원',
      sub: `투자원금 ${fmtKrw(total?.invested_krw)}원`,
      color: 'text-foreground',
    },
    {
      label: '시장 국면',
      value: regime?.regime ?? '—',
      sub: regime?.confidence
        ? `신뢰도 ${(regime.confidence * 100).toFixed(0)}%`
        : '—',
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
    <div className="grid grid-cols-4 sm:grid-cols-2 gap-3">
      {stats.map((s) => (
        <Card key={s.label} className="bg-mc-card border-mc-border">
          <CardContent className="pt-3 pb-3">
            <div className="text-xs text-muted-foreground">{s.label}</div>
            <div className={`text-lg font-mono font-bold mt-0.5 ${s.color}`}>
              {s.value}
            </div>
            <div className="text-xs text-muted-foreground">{s.sub}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/** 보유 종목 테이블 */
function HoldingsTable() {
  const { data, isLoading } = useIntelData()
  const holdings = data?.portfolio_summary?.holdings ?? []

  if (isLoading) {
    return (
      <div className="text-muted-foreground text-xs p-4">로딩 중...</div>
    )
  }

  return (
    <Card className="bg-mc-card border-mc-border">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-xs font-mono">보유 종목</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="border-mc-border hover:bg-transparent">
              <TableHead className="text-xs text-muted-foreground">
                종목명
              </TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">
                현재가
              </TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">
                등락
              </TableHead>
              <TableHead className="text-xs text-muted-foreground text-right hidden sm:table-cell">
                평균단가
              </TableHead>
              <TableHead className="text-xs text-muted-foreground text-right">
                평가손익
              </TableHead>
              <TableHead className="text-xs text-muted-foreground text-right hidden sm:table-cell">
                통화
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {holdings.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground text-xs py-6"
                >
                  보유 종목 없음
                </TableCell>
              </TableRow>
            ) : (
              holdings.map((h) => (
                <TableRow key={h.ticker} className="border-mc-border">
                  <TableCell className="text-xs">
                    <div className="font-medium">{h.name}</div>
                    <div className="text-muted-foreground font-mono">
                      {h.ticker}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-right font-mono">
                    {h.price?.toLocaleString()}
                  </TableCell>
                  <TableCell
                    className={`text-xs text-right font-mono ${pctColor(h.change_pct)}`}
                  >
                    {fmtPct(h.change_pct)}
                  </TableCell>
                  <TableCell className="text-xs text-right font-mono hidden sm:table-cell">
                    {h.avg_price?.toLocaleString() ?? '—'}
                  </TableCell>
                  <TableCell
                    className={`text-xs text-right font-mono ${pctColor(h.pnl_pct)}`}
                  >
                    {fmtPct(h.pnl_pct)}
                    {h.pnl_krw !== undefined && (
                      <div className="text-muted-foreground">
                        {fmtKrw(h.pnl_krw)}원
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-right text-muted-foreground hidden sm:table-cell">
                    {h.currency ?? h.market ?? '—'}
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

/** 시장 국면 + Fear&Greed + 매크로 사이드바 */
function MarketSidebar() {
  const { data } = useIntelData()
  const regime = data?.market_regime
  const supply = data?.supply_data
  const macro = data?.macro ?? []

  const fg = supply?.fear_greed_index
  const fgColor =
    fg !== undefined
      ? fg >= 70
        ? 'text-mc-red'
        : fg >= 50
          ? 'text-amber'
          : fg >= 30
            ? 'text-mc-green'
            : 'text-mc-red'
      : 'text-muted-foreground'

  return (
    <div className="space-y-3">
      {/* 시장 국면 카드 */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-xs font-mono">시장 국면</CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3 space-y-1.5">
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">국면</span>
            <span className="text-xs text-gold font-mono">
              {regime?.regime ?? '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">신뢰도</span>
            <span className="text-xs font-mono">
              {regime?.confidence
                ? `${(regime.confidence * 100).toFixed(0)}%`
                : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">VIX</span>
            <span className="text-xs font-mono">
              {regime?.vix?.toFixed(1) ?? '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs text-muted-foreground">현금비중</span>
            <span className="text-xs font-mono">
              {regime?.cash_ratio
                ? `${(regime.cash_ratio * 100).toFixed(0)}%`
                : '—'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Fear & Greed */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-2 px-3">
          <CardTitle className="text-xs font-mono">Fear & Greed</CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3">
          <div className={`text-2xl font-mono font-bold ${fgColor}`}>
            {fg ?? '—'}
          </div>
          <div className="text-xs text-muted-foreground mb-2">
            {supply?.fear_greed_label ?? ''}
          </div>
          {fg !== undefined && <Progress value={fg} className="h-1.5" />}
        </CardContent>
      </Card>

      {/* 매크로 지표 */}
      {macro.length > 0 && (
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-xs font-mono">매크로</CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3 space-y-1.5">
            {macro.slice(0, 4).map((m) => (
              <div key={m.indicator} className="flex justify-between">
                <span className="text-xs text-muted-foreground">
                  {m.label ?? m.indicator}
                </span>
                <span
                  className={`text-xs font-mono ${pctColor(m.change_pct)}`}
                >
                  {m.value?.toFixed(2)}
                  {m.change_pct !== undefined &&
                    ` (${fmtPct(m.change_pct)})`}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/** 오버뷰 탭 메인 컴포넌트 */
export function OverviewTab() {
  return (
    <div className="space-y-4">
      <StatsStrip />
      <div className="grid grid-cols-[1fr_260px] lg:grid-cols-1 gap-4">
        <div className="space-y-4 order-2 lg:order-1">
          <HoldingsTable />
        </div>
        <div className="order-1 lg:order-2">
          <MarketSidebar />
        </div>
      </div>
    </div>
  )
}
