'use client'

import { useState, useMemo, useCallback } from 'react'
import useSWR from 'swr'
import { ConditionPanel } from '@/components/advisor/ConditionPanel'
import { AIAdvisorPanel } from '@/components/advisor/AIAdvisorPanel'
import { AssetGrid } from '@/components/advisor/AssetGrid'
import type { InvestmentAsset, RiskLevel } from '@/types/advisor'
import investmentAssets from '@/data/investment-assets.json'

const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

const fetcher = (url: string) => fetch(url).then(r => r.json())

/** 포트폴리오에서 AI 리스크 성향 추론 */
function inferRiskLevel(holdings: Array<{ market?: string; current_value_krw?: number }> | undefined): {
  level: RiskLevel
  reason: string
} {
  if (!holdings || holdings.length === 0) {
    return { level: 3, reason: '보유종목 정보 없음, 기본값 적용' }
  }

  const total = holdings.reduce((sum, h) => sum + (h.current_value_krw ?? 0), 0)
  if (total <= 0) return { level: 3, reason: '평가금액 산출 불가' }

  const stockValue = holdings
    .filter(h => h.market === 'KRX' || h.market === 'US')
    .reduce((sum, h) => sum + (h.current_value_krw ?? 0), 0)

  const stockPct = (stockValue / total) * 100

  if (stockPct >= 80) return { level: 4, reason: `주식 비중 ${stockPct.toFixed(0)}% (공격적)` }
  if (stockPct >= 60) return { level: 3, reason: `주식 비중 ${stockPct.toFixed(0)}% (중립)` }
  if (stockPct >= 40) return { level: 2, reason: `주식 비중 ${stockPct.toFixed(0)}% (보수-중립)` }
  return { level: 1, reason: `주식 비중 ${stockPct.toFixed(0)}% (보수적)` }
}

/** 접근 가능한 자산 전체 객체 추출 */
function getAvailableAssets(
  assets: InvestmentAsset[],
  capital: number,
  leverageOn: boolean,
): InvestmentAsset[] {
  return assets.filter(asset => {
    if (asset.status === 'upcoming') return false
    const minRequired = leverageOn && asset.min_capital_leveraged !== null
      ? asset.min_capital_leveraged
      : asset.min_capital
    return minRequired <= capital
  })
}

export function AdvisorTab() {
  const [capital, setCapital] = useState(50_000_000)
  const [leverageAmt, setLeverageAmt] = useState(0)
  const [riskLevel, setRiskLevel] = useState<RiskLevel>(3)

  /* 전재산 데이터 로드 */
  const { data: wealthData } = useSWR(`${BASE}/api/wealth`, fetcher)
  const wealthKrw: number | null = wealthData?.total_wealth_krw ?? null

  /* 포트폴리오 데이터에서 AI 리스크 추론 */
  const { data: intelData } = useSWR(`${BASE}/api/data`, fetcher)
  const holdings = intelData?.portfolio_summary?.holdings

  const aiRisk = useMemo(() => inferRiskLevel(holdings), [holdings])

  const assets = investmentAssets as InvestmentAsset[]

  const leverageOn = leverageAmt > 0
  const availableAssets = useMemo(
    () => getAvailableAssets(assets, capital, leverageOn),
    [assets, capital, leverageOn],
  )

  const stableSetCapital = useCallback((v: number) => setCapital(v), [])

  return (
    <div className="space-y-4">
      {/* Panel 1: 조건 설정 */}
      <ConditionPanel
        capital={capital}
        setCapital={stableSetCapital}
        leverageAmt={leverageAmt}
        setLeverageAmt={setLeverageAmt}
        riskLevel={riskLevel}
        setRiskLevel={setRiskLevel}
        aiRiskLevel={aiRisk.level}
        aiRiskReason={aiRisk.reason}
        wealthKrw={wealthKrw}
      />

      {/* Panel 2: AI 어드바이저 */}
      <AIAdvisorPanel
        capital={capital}
        leverageAmt={leverageAmt}
        riskLevel={riskLevel}
        availableAssets={availableAssets}
      />

      {/* Panel 3: 자산 그리드 */}
      <AssetGrid
        assets={assets}
        capital={capital}
        leverageOn={leverageOn}
      />
    </div>
  )
}
