'use client'

import useSWR from 'swr'
import { fetchProcessStatus } from '@/lib/api'
import type { ProcessStatus } from '@/types/api'

export function useProcessStatus() {
  const { data, error, isLoading } = useSWR<ProcessStatus>(
    'process-status',
    fetchProcessStatus,
    { refreshInterval: 5_000, revalidateOnFocus: false },
  )
  return {
    pipelineRunning: data?.pipeline_running ?? false,
    marcusRunning: data?.marcus_running ?? false,
    data,
    error,
    isLoading,
  }
}
