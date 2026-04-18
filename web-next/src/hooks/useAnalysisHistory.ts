import useSWR from 'swr'
import { fetchAnalysisHistory } from '@/lib/api'
import type { AnalysisHistory } from '@/types/api'

export function useAnalysisHistory() {
  const { data } = useSWR<AnalysisHistory[]>('analysis-history', fetchAnalysisHistory)
  return { history: data ?? [] }
}
