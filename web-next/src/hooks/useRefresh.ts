'use client'

import { useCallback, useState } from 'react'

/**
 * 수동 새로고침 상태와 핸들러를 제공하는 훅
 * mutate: SWR mutate 함수 (데이터 재검증 트리거)
 */
export function useRefresh(mutate: () => Promise<unknown>) {
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    try {
      await mutate()
    } finally {
      setIsRefreshing(false)
    }
  }, [mutate, isRefreshing])

  return { refresh, isRefreshing }
}
