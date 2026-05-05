'use client'

import { useEffect, useRef } from 'react'
import { createChart, LineSeries, ColorType, LineStyle, type IChartApi } from 'lightweight-charts'
import { useTheme } from 'next-themes'
import type { WealthHistoryEntry } from '@/hooks/useWealthData'

interface WealthLineChartProps {
  history: WealthHistoryEntry[]
  height?: number
}

const LEGEND_ITEMS = [
  { label: '전체', color: '#c9a93a' },
  { label: '투자', color: '#3b82f6' },
  { label: '비금융', color: '#e09b3d' },
] as const

export function WealthLineChart({ history, height = 220 }: WealthLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const { theme } = useTheme()
  const isDark = theme !== 'light'

  useEffect(() => {
    const el = containerRef.current
    if (!el || history.length === 0) return

    const textColor = isDark ? '#9a8e84' : '#8a7e74'
    const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)'
    const crosshairColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'

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
      },
      timeScale: {
        borderVisible: false,
      },
      crosshair: {
        vertLine: { color: crosshairColor, style: LineStyle.Dashed },
        horzLine: { color: crosshairColor, style: LineStyle.Dashed },
      },
    })
    chartRef.current = chart

    // Y축 억 단위 포맷
    chart.priceScale('right').applyOptions({
      borderVisible: false,
    })

    // 전체 자산 (gold)
    const totalSeries = chart.addSeries(LineSeries, {
      color: '#c9a93a',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: {
        type: 'custom',
        formatter: (v: number) => `${Math.round(v / 1e8).toLocaleString()}억`,
      },
    })

    // 투자 (blue)
    const investSeries = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: {
        type: 'custom',
        formatter: (v: number) => `${Math.round(v / 1e8).toLocaleString()}억`,
      },
    })

    // 비금융 (amber, dashed)
    const extraSeries = chart.addSeries(LineSeries, {
      color: '#e09b3d',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: {
        type: 'custom',
        formatter: (v: number) => `${Math.round(v / 1e8).toLocaleString()}억`,
      },
    })

    const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date))

    totalSeries.setData(sorted.map(d => ({ time: d.date, value: d.total_wealth_krw })))
    investSeries.setData(sorted.map(d => ({ time: d.date, value: d.investment_value_krw })))
    extraSeries.setData(sorted.map(d => ({ time: d.date, value: d.extra_assets_krw })))

    chart.timeScale().fitContent()

    // ResizeObserver
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        chart.resize(entry.contentRect.width, height)
      }
    })
    observer.observe(el)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [history, height, isDark])

  return (
    <div className="relative">
      {/* 범례 */}
      <div className="absolute top-1 right-1 z-10 flex items-center gap-3">
        {LEGEND_ITEMS.map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-xs font-mono text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      <div ref={containerRef} />
    </div>
  )
}
