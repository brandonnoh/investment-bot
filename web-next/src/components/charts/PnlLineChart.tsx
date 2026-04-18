'use client'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
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
        <YAxis tick={{ fontSize: 10, fill: '#9a8e84' }} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip
          contentStyle={{ background: '#131210', border: '1px solid #2a2420', borderRadius: 4 }}
          formatter={(v?: ValueType) => [`${v ?? 0}%`, '손익률']}
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
