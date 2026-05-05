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

function SparklineSvg({ data, height }: { data: PricePoint[]; height: number }) {
  if (data.length < 2) return null

  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date))
  const values = sorted.map(d => d.close)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const W = 100  // viewBox width
  const H = height
  const pad = 2

  const points = sorted.map((d, i) => {
    const x = pad + (i / (sorted.length - 1)) * (W - pad * 2)
    const y = (H - pad) - ((d.close - min) / range) * (H - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  const isUp = values[values.length - 1] >= values[0]
  const color = isUp ? '#4dca7e' : '#e05656'

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height, display: 'block' }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function PriceSparkline({ ticker, days = 30, height = 48 }: PriceSparklineProps) {
  const { data } = useSWR<PricePoint[]>(
    `/api/price-history?ticker=${ticker}&days=${days}`,
    fetcher,
    { dedupingInterval: 300_000 }
  )

  if (!data) {
    return <div className="rounded bg-muted animate-pulse" style={{ height }} />
  }

  if (data.length < 2) {
    return null
  }

  return (
    <div style={{ height }}>
      <SparklineSvg data={data} height={height} />
    </div>
  )
}
