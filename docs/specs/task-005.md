# task-005: 포트폴리오 탭 — 손익 추이 차트 + 섹터 파이 차트

## 배경
현재 web/index.html 포트폴리오 탭(줄 277 이후)과 app.js의 Chart.js 코드(줄 157-300)를 Recharts로 교체.

## 현재 Chart.js 코드 (app.js 줄 157-255)
- `chart-portfolio` canvas: 손익 추이 LineChart (x=날짜, y=pnl_pct)
- `chart-sector` canvas: 섹터 파이 PieChart (holdings 기반)

## 구현 방향

### web-next/src/components/tabs/PortfolioTab.tsx

```typescript
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
      {/* 요약 카드 4개 */}
      <div className="grid grid-cols-4 sm:grid-cols-2 gap-3">
        <SummaryCard label="투자원금" value={fmtKrw(total?.invested_krw)} />
        <SummaryCard label="평가금액" value={fmtKrw(total?.total_value_krw)} />
        <SummaryCard label="총 손익" value={fmtKrw(total?.pnl_krw)} color={pctColor(total?.pnl_pct)} />
        <SummaryCard label="수익률" value={fmtPct(total?.pnl_pct)} color={pctColor(total?.pnl_pct)} large />
      </div>

      {/* 차트 2개 */}
      <div className="grid grid-cols-[3fr_2fr] gap-4 lg:grid-cols-1">
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs">수익률 추이</CardTitle>
          </CardHeader>
          <CardContent>
            <PnlLineChart history={history} />
          </CardContent>
        </Card>

        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs">섹터 비중</CardTitle>
          </CardHeader>
          <CardContent>
            <SectorPieChart holdings={holdings} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

### web-next/src/components/charts/PnlLineChart.tsx
```typescript
'use client'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { PortfolioHistory } from '@/types/api'

export function PnlLineChart({ history }: { history: PortfolioHistory[] }) {
  const data = history.map(h => ({
    date: h.date.slice(5),  // MM-DD
    pnl: +(h.pnl_pct ?? h.total_pnl_pct ?? 0).toFixed(2),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data}>
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9a8e84' }} />
        <YAxis tick={{ fontSize: 10, fill: '#9a8e84' }} tickFormatter={v => `${v}%`} />
        <Tooltip
          contentStyle={{ background: '#131210', border: '1px solid #2a2420', borderRadius: 4 }}
          formatter={(v: number) => [`${v}%`, '손익률']}
        />
        <ReferenceLine y={0} stroke="#2a2420" />
        <Line
          type="monotone"
          dataKey="pnl"
          stroke="#c9a93a"
          strokeWidth={2}
          dot={{ fill: '#c9a93a', r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### web-next/src/components/charts/SectorPieChart.tsx
```typescript
'use client'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { PriceItem } from '@/types/api'

const COLORS = ['#c9a93a', '#4dca7e', '#4ec9b0', '#e09b3d', '#e05656', '#9a8e84']

export function SectorPieChart({ holdings }: { holdings: PriceItem[] }) {
  // market 기준으로 섹터 집계 (현재 holdings에 sector 없으면 market 사용)
  const sectorMap: Record<string, number> = {}
  holdings.forEach(h => {
    const key = h.market ?? '기타'
    sectorMap[key] = (sectorMap[key] ?? 0) + 1
  })
  const data = Object.entries(sectorMap).map(([name, value]) => ({ name, value }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip contentStyle={{ background: '#131210', border: '1px solid #2a2420' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
```

## 검증
```bash
cd web-next && npm run build
```
