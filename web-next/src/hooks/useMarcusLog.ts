'use client'

import useSWR from 'swr'
import { fetchLogs } from '@/lib/api'
import type { LogResponse } from '@/types/api'

export function useMarcusLog(enabled: boolean) {
  const { data } = useSWR<LogResponse>(
    enabled ? 'marcus-log' : null,
    () => fetchLogs('marcus', 100),
    { refreshInterval: 3_000 },
  )
  return data?.lines ?? []
}
