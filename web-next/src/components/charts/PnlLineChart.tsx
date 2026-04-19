'use client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import type { ValueType } from 'recharts/types/component/DefaultTooltipContent'
import type { PortfolioHistory } from '@/types/api'
import { useTheme } from 'next-themes'

export function PnlLineChart({ history }: { history: PortfolioHistory[] }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const tooltipBg = isDark ? '#131210' : '#ffffff'
  const tooltipBorder = isDark ? '#2a2420' : '#e8e0d8'
  const tooltipText = isDark ? '#e2d9d0' : '#1a1210'
  const tickColor = isDark ? '#9a8e84' : '#8a7e74'
  const refLineColor = isDark ? '#2a2420' : '#e8e0d8'
  const cursorColor = isDark ? 'rgba(42,36,32,0.4)' : 'rgba(200,190,180,0.3)'

  const data = history.map(h => ({
    date: h.date.slice(5),
    pnl: +(h.total_pnl_pct ?? 0).toFixed(2),
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} barSize={6}>
        <XAxis dataKey="date" tick={{ fontSize: 9, fill: tickColor }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 9, fill: tickColor }} tickFormatter={(v: number) => `${v}%`} tickLine={false} axisLine={false} width={36} />
        <Tooltip
          contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 4 }}
          labelStyle={{ color: tooltipText, fontSize: 11, fontWeight: 600 }}
          itemStyle={{ color: tooltipText, fontSize: 11 }}
          cursor={{ fill: cursorColor }}
          formatter={(v?: ValueType) => [`${v ?? 0}%`, '손익률']}
        />
        <ReferenceLine y={0} stroke={refLineColor} strokeWidth={1} />
        <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? '#4dca7e' : '#e05656'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
