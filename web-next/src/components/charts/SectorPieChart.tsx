'use client'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { PriceItem } from '@/types/api'
import { fmtKrw } from '@/lib/format'

const COLORS = ['#c9a93a', '#4dca7e', '#4ec9b0', '#e09b3d', '#e05656', '#9a8e84']

interface SectorEntry {
  name: string
  value: number
}

export function SectorPieChart({ holdings }: { holdings: PriceItem[] }) {
  const sectorMap: Record<string, number> = {}
  holdings.forEach(h => {
    const key = h.sector ?? h.market ?? '기타'
    sectorMap[key] = (sectorMap[key] ?? 0) + (h.current_value_krw ?? 1)
  })
  const data: SectorEntry[] = Object.entries(sectorMap).map(([name, value]) => ({ name, value }))
  const total = data.reduce((s, d) => s + d.value, 0)

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[180px] text-muted-foreground text-xs">데이터 없음</div>
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={42}
            outerRadius={72}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#131210', border: '1px solid #2a2420', borderRadius: 4 }}
            formatter={(v) => [fmtKrw(v as number) + '원', '']}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-3 gap-y-1.5 justify-center mt-2 px-2">
        {data.map((entry, i) => (
          <span key={entry.name} className="flex items-center gap-1">
            <span
              style={{ backgroundColor: COLORS[i % COLORS.length] }}
              className="inline-block w-2 h-2 rounded-full shrink-0"
            />
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {entry.name} {total > 0 ? ((entry.value / total) * 100).toFixed(0) : 0}%
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}
