'use client'

import { useEffect } from 'react'
import { useSWRConfig } from 'swr'
import { useMCStore } from '@/store/useMCStore'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

export function useSSE() {
  const { mutate } = useSWRConfig()
  const { setSseStatus, setLastUpdated } = useMCStore()

  useEffect(() => {
    const es = new EventSource(`${BASE}/api/events`)

    es.onopen = () => setSseStatus('connected')
    es.onerror = () => setSseStatus('disconnected')

    es.onmessage = () => {
      void mutate('intel-data')
      void mutate('process-status')
      setLastUpdated(
        new Date().toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      )
    }

    return () => es.close()
  }, [mutate, setSseStatus, setLastUpdated])
}
