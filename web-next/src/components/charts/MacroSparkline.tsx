'use client'

interface MacroSparklineProps {
  data?: { time: string; value: number }[]
  width?: number
  height?: number
}

/** 매크로 지표용 SVG 스파크라인 — 데이터 방향에 따라 색상 결정 */
export function MacroSparkline({ data, width = 80, height = 32 }: MacroSparklineProps) {
  if (!data || data.length < 2) {
    return (
      <div
        className="rounded bg-muted animate-pulse"
        style={{ width, height }}
      />
    )
  }

  const values = data.map(d => d.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const W = width
  const H = height
  const pad = 2

  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (W - pad * 2)
      const y = (H - pad) - ((v - min) / range) * (H - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const isUp = values[values.length - 1] >= values[0]
  const color = isUp ? '#3b82f6' : '#e05656'

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      width={width}
      height={height}
      style={{ display: 'block' }}
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
