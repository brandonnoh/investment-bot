'use client'

import useSWR from 'swr'

interface PricePoint {
  date: string
  close: number
}

interface PriceSparklineProps {
  ticker: string
  days?: number
  height?: number
}

const fetcher = (url: string) => fetch(url).then(r => r.json())

function SparklineSvg({ data, height, gradientId }: { data: PricePoint[]; height: number; gradientId: string }) {
  if (data.length < 2) return null

  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date))
  const values = sorted.map(d => d.close)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const W = 100
  const H = height
  const padX = 0
  const padY = 2

  const pts = sorted.map((d, i) => ({
    x: padX + (i / (sorted.length - 1)) * (W - padX * 2),
    y: (H - padY) - ((d.close - min) / range) * (H - padY * 2),
  }))

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L${pts[pts.length - 1].x.toFixed(1)},${H} L${pts[0].x.toFixed(1)},${H} Z`

  const isUp = values[values.length - 1] >= values[0]
  const color = isUp ? '#4dca7e' : '#e05656'

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full" style={{ height, display: 'block' }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={linePath} fill="none" stroke={color} strokeWidth="1.2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

export function PriceSparkline({ ticker, days = 30, height = 40 }: PriceSparklineProps) {
  const gradientId = `sg-${ticker.replace(/[^a-zA-Z0-9]/g, '_')}`

  const { data } = useSWR<PricePoint[]>(
    `/api/price-history?ticker=${ticker}&days=${days}`,
    fetcher,
    { dedupingInterval: 300_000 }
  )

  if (!data) return <div className="rounded animate-pulse bg-mc-border/30" style={{ height }} />
  if (data.length < 2) return null

  return (
    <div style={{ height }}>
      <SparklineSvg data={data} height={height} gradientId={gradientId} />
    </div>
  )
}
