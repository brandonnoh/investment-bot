'use client'

import { useCallback, useState } from 'react'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''
const REFRESH_DURATION_MS = 15_000

async function triggerRefreshPrices(): Promise<void> {
  const res = await fetch(`${BASE}/api/refresh-prices`, { method: 'POST' })
  if (!res.ok) throw new Error(`refresh-prices 실패: ${res.status}`)
  // refresh_prices.py 실행 시간(~12초) 대기 후 SSE가 완료를 알려줌
  await new Promise<void>((resolve) => setTimeout(resolve, REFRESH_DURATION_MS))
}

export function useRefresh(mutate: () => Promise<unknown>) {
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    try {
      await triggerRefreshPrices()
      await mutate()
    } catch (e) {
      console.error('refresh 실패:', e)
      await mutate()
    } finally {
      setIsRefreshing(false)
    }
  }, [mutate, isRefreshing])

  return { refresh, isRefreshing }
}
