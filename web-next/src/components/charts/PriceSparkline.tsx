'use client'

import { useEffect, useRef } from 'react'
import useSWR from 'swr'
import { createChart, LineSeries, ColorType } from 'lightweight-charts'
import { useTheme } from 'next-themes'

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

export function PriceSparkline({ ticker, days = 30, height = 48 }: PriceSparklineProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { theme } = useTheme()
  const isDark = theme !== 'light'
  const { data } = useSWR<PricePoint[]>(
    `/api/price-history?ticker=${ticker}&days=${days}`,
    fetcher,
    { dedupingInterval: 300_000 }
  )

  useEffect(() => {
    const el = containerRef.current
    if (!el || !data || data.length === 0) return

    const width = el.clientWidth
    if (width === 0) return

    const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date))
    const firstVal = sorted[0].close
    const lastVal = sorted[sorted.length - 1].close
    const lineColor = lastVal >= firstVal ? '#4dca7e' : '#e05656'

    const chart = createChart(el, {
      width,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'transparent',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { visible: false },
      leftPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
      handleScroll: false,
      handleScale: false,
    })

    const series = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    series.setData(sorted.map(d => ({ time: d.date, value: d.close })))
    chart.timeScale().fitContent()

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) chart.resize(entry.contentRect.width, height)
    })
    observer.observe(el)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [data, height, isDark])

  // 로딩 또는 데이터 없음
  if (!data || data.length === 0) {
    return (
      <div
        className="rounded bg-muted animate-pulse"
        style={{ height }}
      />
    )
  }

  return <div ref={containerRef} />
}
