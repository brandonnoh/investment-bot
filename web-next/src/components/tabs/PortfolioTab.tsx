'use client'
import { useIntelData } from '@/hooks/useIntelData'
import { PnlLineChart } from '@/components/charts/PnlLineChart'
import { SectorPieChart } from '@/components/charts/SectorPieChart'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'

export function PortfolioTab() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const history = data?.portfolio_summary?.history ?? []
  const holdings = data?.portfolio_summary?.holdings ?? []

  return (
    <div className="space-y-4">
      {/* 요약 칩 - 모바일 수평 스크롤, 데스크탑 4열 grid */}
      <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 lg:grid lg:grid-cols-4 lg:overflow-visible lg:pb-0 lg:mx-0 lg:px-0 lg:gap-3">
        {([
          { label: '투자원금', value: `${fmtKrw(total?.invested_krw)}원`, color: undefined },
          { label: '평가금액', value: `${fmtKrw(total?.current_value_krw)}원`, color: undefined },
          { label: '총 손익',  value: `${fmtKrw(total?.pnl_krw)}원`, color: pctColor(total?.pnl_pct) },
          { label: '수익률',   value: fmtPct(total?.pnl_pct), color: pctColor(total?.pnl_pct) },
        ] as const).map(({ label, value, color }) => (
          <div key={label} className="shrink-0 bg-mc-card border border-mc-border rounded-lg px-4 py-3 min-w-[130px] lg:min-w-0">
            <div className="text-[11px] text-muted-foreground whitespace-nowrap">{label}</div>
            <div className={`text-sm font-mono font-bold mt-0.5 whitespace-nowrap ${color ?? 'text-foreground'}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* 차트 2개 */}
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-4">
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">수익률 추이</CardTitle>
          </CardHeader>
          <CardContent>
            <PnlLineChart history={history} />
          </CardContent>
        </Card>

        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">섹터 비중</CardTitle>
          </CardHeader>
          <CardContent>
            <SectorPieChart holdings={holdings} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
