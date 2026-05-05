'use client'

import { useEffect, useRef } from 'react'

interface TradingViewWidgetProps {
  ticker: string
  height?: number
}

function toTvSymbol(ticker: string): string {
  const code = ticker.replace(/\.(KS|KQ)$/, '')
  if (ticker.endsWith('.KS') || ticker.endsWith('.KQ')) return `KRX:${code}`
  return ticker
}

export function TradingViewWidget({ ticker, height = 350 }: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    // 기존 내용 초기화
    el.innerHTML = ''

    const widgetContainer = document.createElement('div')
    widgetContainer.className = 'tradingview-widget-container'

    const widgetEl = document.createElement('div')
    widgetEl.className = 'tradingview-widget-container__widget'
    widgetContainer.appendChild(widgetEl)

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbol: toTvSymbol(ticker),
      width: '100%',
      height,
      locale: 'kr',
      dateRange: '3M',
      colorTheme: 'dark',
      isTransparent: true,
      autosize: true,
      largeChartUrl: '',
    })

    widgetContainer.appendChild(script)
    el.appendChild(widgetContainer)

    return () => {
      if (el) el.innerHTML = ''
    }
  }, [ticker, height])

  return <div ref={containerRef} style={{ height, minHeight: height }} />
}
