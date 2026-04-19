'use client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import type { ValueType } from 'recharts/types/component/DefaultTooltipContent'
import type { PortfolioHistory } from '@/types/api'

export function PnlLineChart({ history }: { history: PortfolioHistory[] }) {
  const data = history.map(h => ({
    date: h.date.slice(5),
    pnl: +(h.total_pnl_pct ?? 0).toFixed(2),
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} barSize={6}>
        <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#9a8e84' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 9, fill: '#9a8e84' }} tickFormatter={(v: number) => `${v}%`} tickLine={false} axisLine={false} width={36} />
        <Tooltip
          contentStyle={{ background: '#131210', border: '1px solid #2a2420', borderRadius: 4 }}
          formatter={(v?: ValueType) => [`${v ?? 0}%`, '손익률']}
        />
        <ReferenceLine y={0} stroke="#2a2420" strokeWidth={1} />
        <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? '#4dca7e' : '#e05656'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
