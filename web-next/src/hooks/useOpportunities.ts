'use client'

import useSWR from 'swr'
import { fetchOpportunities } from '@/lib/api'

export const STRATEGIES = [
  {
    id: 'composite',
    name: '퀀트',
    description: '5개 팩터 종합 점수 (기본값)',
    criteria: ['수익성 30%', '가치 25%', '수급 20%', '기술 15%', '성장 10%', '60점 이상 통과'],
  },
  {
    id: 'graham',
    name: '그레이엄',
    description: '저평가 자산, 강한 안전마진',
    criteria: ['PER ≤ 15', 'PBR ≤ 1.5', 'PER×PBR ≤ 22.5', '부채비율 ≤ 100%'],
  },
  {
    id: 'buffett',
    name: '버핏',
    description: '우량 기업, 장기 보유, 경제적 해자',
    criteria: ['ROE ≥ 15%', '영업이익률 ≥ 15%', '부채비율 ≤ 50%', 'EPS 흑자'],
  },
  {
    id: 'lynch',
    name: '린치',
    description: '성장+합리적 가격 (GARP)',
    criteria: ['매출성장률 15~50%', 'PEG대용 ≤ 1.5', '부채비율 ≤ 60%'],
  },
  {
    id: 'greenblatt',
    name: '그린블랫',
    description: '수익률+자본효율 상위 (매직포뮬라)',
    criteria: ['PER 낮은 순위', 'ROE 높은 순위', '두 순위 합산 상위 30종목'],
  },
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
