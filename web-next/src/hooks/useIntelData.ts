'use client'

import useSWR from 'swr'
import { fetchIntelData } from '@/lib/api'
import type { IntelData } from '@/types/api'

export function useIntelData() {
  const { data, error, isLoading, mutate } = useSWR<IntelData>(
    'intel-data',
    fetchIntelData,
    { refreshInterval: 0, revalidateOnFocus: false },
  )
  return { data, error, isLoading, mutate }
}
