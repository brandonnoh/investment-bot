'use client'
import type { PriceItem } from '@/types/api'

const COLORS = ['#c9a93a', '#4dca7e', '#4ec9b0', '#e09b3d', '#e05656', '#9a8e84', '#7b6fa0']

interface SectorEntry { name: string; value: number }

export function SectorPieChart({ holdings }: { holdings: PriceItem[] }) {
  const sectorMap: Record<string, number> = {}
  holdings.forEach(h => {
    const key = h.sector ?? h.market ?? '기타'
    sectorMap[key] = (sectorMap[key] ?? 0) + (h.current_value_krw ?? 1)
  })
  const data: SectorEntry[] = Object.entries(sectorMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }))
  const total = data.reduce((s, d) => s + d.value, 0)

  if (data.length === 0) {
    return <div className="text-muted-foreground text-xs text-center py-6">데이터 없음</div>
  }

  return (
    <div className="space-y-3">
      {/* 누적 가로 막대 */}
      <div className="flex h-6 rounded-md overflow-hidden gap-px">
        {data.map((entry, i) => (
          <div
            key={entry.name}
            style={{
              width: `${(entry.value / total) * 100}%`,
              backgroundColor: COLORS[i % COLORS.length],
              minWidth: entry.value / total > 0.02 ? undefined : '2px',
            }}
            title={`${entry.name} ${((entry.value / total) * 100).toFixed(1)}%`}
          />
        ))}
      </div>
      {/* 범례 */}
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {data.map((entry, i) => (
          <span key={entry.name} className="flex items-center gap-1">
            <span
              style={{ backgroundColor: COLORS[i % COLORS.length] }}
              className="inline-block w-2 h-2 rounded-sm shrink-0"
            />
            <span className="text-[11px] text-muted-foreground whitespace-nowrap">
              {entry.name} <span className="text-foreground font-mono">{((entry.value / total) * 100).toFixed(0)}%</span>
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}
