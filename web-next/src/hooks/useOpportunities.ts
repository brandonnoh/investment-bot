'use client'

import useSWR from 'swr'
import { fetchOpportunities } from '@/lib/api'

export const STRATEGIES = [
  { id: 'composite', name: '퀀트', description: '5개 팩터 종합 점수 (기본값)' },
  { id: 'graham', name: '그레이엄', description: '저평가 자산, 강한 안전마진' },
  { id: 'buffett', name: '버핏', description: '우량 기업, 장기 보유, 경제적 해자' },
  { id: 'lynch', name: '린치', description: '성장+합리적 가격 (GARP)' },
  { id: 'greenblatt', name: '그린블랫', description: '수익률+자본효율 상위 (매직포뮬라)' },
] as const

export type StrategyId = (typeof STRATEGIES)[number]['id']

export function useOpportunities(strategy: StrategyId) {
  const { data, error, isLoading } = useSWR(
    `opportunities-${strategy}`,
    () => fetchOpportunities(strategy),
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  )
  return {
    opportunities: data?.opportunities ?? [],
    meta: data?.meta,
    isLoading,
    error,
  }
}
