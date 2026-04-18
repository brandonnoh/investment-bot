'use client'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { PieLabelRenderProps } from 'recharts'
import type { PriceItem } from '@/types/api'

const COLORS = ['#c9a93a', '#4dca7e', '#4ec9b0', '#e09b3d', '#e05656', '#9a8e84']

interface SectorEntry {
  name: string
  value: number
}

export function SectorPieChart({ holdings }: { holdings: PriceItem[] }) {
  const sectorMap: Record<string, number> = {}
  holdings.forEach(h => {
    const key = h.market ?? '기타'
    sectorMap[key] = (sectorMap[key] ?? 0) + 1
  })
  const data: SectorEntry[] = Object.entries(sectorMap).map(([name, value]) => ({ name, value }))

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[220px] text-muted-foreground text-xs">데이터 없음</div>
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          outerRadius={80}
          dataKey="value"
          label={({ name, percent }: PieLabelRenderProps) => `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip contentStyle={{ background: '#131210', border: '1px solid #2a2420' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
