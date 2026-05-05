'use client'

interface MacroSparklineProps {
  data?: { time: string; value: number }[]
  positive?: boolean
  width?: number
  height?: number
}

export function MacroSparkline({ data, positive = true, width = 80, height = 32 }: MacroSparklineProps) {
  // data가 없거나 비어 있으면 skeleton
  if (!data || data.length === 0) {
    return (
      <div
        className="rounded bg-muted animate-pulse"
        style={{ width, height }}
      />
    )
  }
  // TODO: Phase C에서 실 데이터 연결 (lightweight-charts LineSeries)
  return (
    <div
      className="rounded bg-muted"
      style={{ width, height }}
    />
  )
}
