'use client'
import { useIntelData } from '@/hooks/useIntelData'
import { PnlLineChart } from '@/components/charts/PnlLineChart'
import { SectorPieChart } from '@/components/charts/SectorPieChart'
import { AssetTypeBar } from '@/components/charts/AssetTypeBar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtKrw, fmtPct, pctColor } from '@/lib/format'

export function PortfolioTab() {
  const { data } = useIntelData()
  const total = data?.portfolio_summary?.total
  const history = data?.portfolio_summary?.history ?? []
  const holdings = data?.portfolio_summary?.holdings ?? []

  return (
    <div className="space-y-4">
      {/* 요약 카드 - 항상 2x2 grid */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: '투자원금', value: `${fmtKrw(total?.invested_krw)}원`, color: undefined },
          { label: '평가금액', value: `${fmtKrw(total?.current_value_krw)}원`, color: undefined },
          { label: '총 손익',  value: `${fmtKrw(total?.pnl_krw)}원`, color: pctColor(total?.pnl_pct) },
          { label: '수익률',   value: fmtPct(total?.pnl_pct), color: pctColor(total?.pnl_pct) },
        ].map(({ label, value, color }) => (
          <Card key={label} className="bg-mc-card border-mc-border">
            <CardContent className="pt-3 pb-3 px-4">
              <div className="text-xs text-muted-foreground">{label}</div>
              <div className={`text-sm font-mono font-bold mt-0.5 ${color ?? 'text-foreground'}`}>{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 차트 3개: 수익률 추이 + 섹터 비중 + 자산 종류 */}
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-4">
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">수익률 추이</CardTitle>
          </CardHeader>
          <CardContent>
            <PnlLineChart history={history} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="bg-mc-card border-mc-border">
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-xs font-mono">섹터 비중</CardTitle>
            </CardHeader>
            <CardContent>
              <SectorPieChart holdings={holdings} />
            </CardContent>
          </Card>

          <Card className="bg-mc-card border-mc-border">
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-xs font-mono">자산 종류</CardTitle>
            </CardHeader>
            <CardContent>
              <AssetTypeBar holdings={holdings} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
