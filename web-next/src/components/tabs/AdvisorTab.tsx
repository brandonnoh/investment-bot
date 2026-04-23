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

  const { data: wealthData } = useSWR(`${BASE}/api/wealth`, fetcher)
  const wealthKrw: number | null = wealthData?.total_wealth_krw ?? null

  const assets = investmentAssets as InvestmentAsset[]
  const leverageOn = leverageAmt > 0
  const availableAssets = useMemo(
    () => getAvailableAssets(assets, capital, leverageOn),
    [assets, capital, leverageOn],
  )

  const stableSetCapital = useCallback((v: number) => setCapital(v), [])

  return (
    <div className="space-y-4">
      <ConditionPanel
        capital={capital}
        setCapital={stableSetCapital}
        leverageAmt={leverageAmt}
        setLeverageAmt={setLeverageAmt}
        riskLevel={riskLevel}
        setRiskLevel={setRiskLevel}
        wealthKrw={wealthKrw}
      />

      <AIAdvisorPanel
        capital={capital}
        leverageAmt={leverageAmt}
        riskLevel={riskLevel}
        availableAssets={availableAssets}
      />

      <AssetGrid
        assets={assets}
        capital={capital}
        leverageOn={leverageOn}
      />
    </div>
  )
}
