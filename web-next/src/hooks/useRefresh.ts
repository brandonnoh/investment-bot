'use client'

import { useCallback, useState } from 'react'

export function useRefresh(mutate: () => Promise<unknown>) {
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    try {
      // cron이 1분마다 미리 수집 → 끌어서 새로고침은 캐시된 최신 데이터 즉시 반환
      await mutate()
    } catch (e) {
      console.error('refresh 실패:', e)
    } finally {
      setIsRefreshing(false)
    }
  }, [mutate, isRefreshing])

  return { refresh, isRefreshing }
}
