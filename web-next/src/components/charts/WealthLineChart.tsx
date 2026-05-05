'use client'

import { useEffect, useRef } from 'react'
import { createChart, LineSeries, ColorType, LineStyle, type IChartApi } from 'lightweight-charts'
import { useTheme } from 'next-themes'
import type { WealthHistoryEntry } from '@/hooks/useWealthData'

interface WealthLineChartProps {
  history: WealthHistoryEntry[]
  height?: number
}

const SERIES_CFG = [
  { key: 'total_wealth_krw',    label: '전체',   color: '#c9a93a', lineWidth: 2 as const, lineStyle: LineStyle.Solid },
  { key: 'extra_assets_krw',    label: '비금융', color: '#e09b3d', lineWidth: 1 as const, lineStyle: LineStyle.Dashed },
  { key: 'investment_value_krw',label: '투자',   color: '#3b82f6', lineWidth: 1 as const, lineStyle: LineStyle.Solid },
] as const

function fmtAmt(v: number): string {
  const eok = v / 1e8
  if (Math.abs(eok) >= 1) return `${eok.toFixed(1)}억`
  return `${(v / 1e4).toFixed(0)}만`
}

export function WealthLineChart({ history, height = 200 }: WealthLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const { theme } = useTheme()
  const isDark = theme !== 'light'

  useEffect(() => {
    const el = containerRef.current
    if (!el || history.length === 0) return

    const textColor = isDark ? '#9a8e84' : '#8a7e74'
    const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)'
    const crosshairColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'

    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: gridColor },
        horzLines: { color: gridColor },
      },
      rightPriceScale: {
        borderVisible: false,
        minimumWidth: 56,
      },
      timeScale: {
        borderVisible: false,
      },
      crosshair: {
        vertLine: { color: crosshairColor, style: LineStyle.Dashed, width: 1 },
        horzLine: { color: crosshairColor, style: LineStyle.Dashed, width: 1 },
      },
    })
    chartRef.current = chart

    const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date))

    for (const cfg of SERIES_CFG) {
      const series = chart.addSeries(LineSeries, {
        color: cfg.color,
        lineWidth: cfg.lineWidth,
        lineStyle: cfg.lineStyle,
        priceLineVisible: false,
        lastValueVisible: true,
        priceFormat: {
          type: 'custom',
          formatter: fmtAmt,
        },
      })
      series.setData(sorted.map(d => ({
        time: d.date,
        value: (d as unknown as Record<string, number>)[cfg.key],
      })))
    }

    chart.timeScale().fitContent()

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) chart.resize(entry.contentRect.width, height)
    })
    observer.observe(el)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [history, height, isDark])

  return (
    <div>
      {/* 범례 — 차트 위 별도 행 */}
      <div className="flex items-center gap-4 mb-2 px-1">
        {SERIES_CFG.map(({ label, color, lineStyle }) => (
          <div key={label} className="flex items-center gap-1.5">
            <svg width="16" height="8" viewBox="0 0 16 8">
              <line
                x1="0" y1="4" x2="16" y2="4"
                stroke={color}
                strokeWidth="2"
                strokeDasharray={lineStyle === LineStyle.Dashed ? '3 2' : undefined}
              />
            </svg>
            <span className="text-[11px] font-mono text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      <div ref={containerRef} />
    </div>
  )
}
