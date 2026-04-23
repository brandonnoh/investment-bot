'use client'

import { useState, useMemo, useCallback, useEffect } from 'react'
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

const LS_KEY = 'mc-advisor-settings'

function loadSettings(): { capital: number; leverageAmt: number; riskLevel: RiskLevel } | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(LS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveSettings(capital: number, leverageAmt: number, riskLevel: RiskLevel) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ capital, leverageAmt, riskLevel }))
  } catch {}
}

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
  const saved = loadSettings()
  const [capital, setCapital] = useState(saved?.capital ?? 50_000_000)
  const [leverageAmt, setLeverageAmt] = useState(saved?.leverageAmt ?? 0)
  const [riskLevel, setRiskLevel] = useState<RiskLevel>(saved?.riskLevel ?? 3)
  const [wealthApplied, setWealthApplied] = useState(false)

  const { data: wealthData } = useSWR(`${BASE}/api/wealth`, fetcher)
  const wealthKrw: number | null = wealthData?.total_wealth_krw ?? null

  // 전재산 로드 시 한 번만 자본금 초기화 (사용자가 직접 설정한 적 없을 때만)
  useEffect(() => {
    if (wealthKrw && wealthKrw > 0 && !wealthApplied && !saved) {
      const snapped = Math.round(Math.min(wealthKrw, 300_000_000) / 5_000_000) * 5_000_000
      setCapital(snapped)
      setWealthApplied(true)
    }
  }, [wealthKrw, wealthApplied, saved])

  // 설정 변경 시 localStorage 저장
  useEffect(() => {
    saveSettings(capital, leverageAmt, riskLevel)
  }, [capital, leverageAmt, riskLevel])

  const assets = investmentAssets as InvestmentAsset[]
  const leverageOn = leverageAmt > 0
  const availableAssets = useMemo(
    () => getAvailableAssets(assets, capital, leverageOn),
    [assets, capital, leverageOn],
  )

  const stableSetCapital = useCallback((v: number) => setCapital(v), [])
  const stableSetLeverageAmt = useCallback((v: number) => setLeverageAmt(v), [])
  const stableSetRiskLevel = useCallback((v: RiskLevel) => setRiskLevel(v), [])

  return (
    <div className="space-y-4">
      <ConditionPanel
        capital={capital}
        setCapital={stableSetCapital}
        leverageAmt={leverageAmt}
        setLeverageAmt={stableSetLeverageAmt}
        riskLevel={riskLevel}
        setRiskLevel={stableSetRiskLevel}
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
