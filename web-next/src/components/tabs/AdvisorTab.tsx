'use client'

import { useState, useMemo, useCallback, useEffect } from 'react'
import useSWR from 'swr'
import { ConditionPanel } from '@/components/advisor/ConditionPanel'
import { AIAdvisorPanel } from '@/components/advisor/AIAdvisorPanel'
import { AssetGrid } from '@/components/advisor/AssetGrid'
import type { InvestmentAsset, RiskLevel, MinusLoanConfig, CreditLoanConfig, PortfolioMode } from '@/types/advisor'

const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

const fetcher = (url: string) => fetch(url).then(r => r.json())

const LS_KEY = 'mc-advisor-settings'

interface SavedSettings {
  capital: number
  riskLevel: RiskLevel
  minusLoan?: MinusLoanConfig | null
  creditLoan?: CreditLoanConfig | null
  monthlySavings?: number
  portfolioMode?: PortfolioMode
  leverageAmt?: number   // 구 형식 호환
}

function loadSettings(): SavedSettings | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(LS_KEY)
    return raw ? (JSON.parse(raw) as SavedSettings) : null
  } catch {
    return null
  }
}

function saveSettings(
  capital: number,
  riskLevel: RiskLevel,
  minusLoan: MinusLoanConfig | null,
  creditLoan: CreditLoanConfig | null,
  monthlySavings: number,
  portfolioMode: PortfolioMode,
) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ capital, riskLevel, minusLoan, creditLoan, monthlySavings, portfolioMode }))
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
  const [capital, setCapital] = useState(50_000_000)
  const [minusLoan, setMinusLoan] = useState<MinusLoanConfig | null>(null)
  const [creditLoan, setCreditLoan] = useState<CreditLoanConfig | null>(null)
  const [monthlySavings, setMonthlySavings] = useState(0)
  const [riskLevel, setRiskLevel] = useState<RiskLevel>(3)
  const [portfolioMode, setPortfolioMode] = useState<PortfolioMode>('include')
  const [wealthApplied, setWealthApplied] = useState(false)

  // localStorage는 마운트 후에만 읽어야 SSR hydration 불일치를 막는다
  useEffect(() => {
    const saved = loadSettings()
    if (!saved) return
    setCapital(saved.capital)
    setRiskLevel(saved.riskLevel)
    setMonthlySavings(saved.monthlySavings ?? 0)
    if ('minusLoan' in saved) {
      setMinusLoan(saved.minusLoan ?? null)
      setCreditLoan(saved.creditLoan ?? null)
    } else if (saved.leverageAmt && saved.leverageAmt > 0) {
      // 구 형식: leverageAmt → 마이너스통장으로 마이그레이션
      setMinusLoan({ amount: saved.leverageAmt, rate: 4.0 })
    }
    if (saved.portfolioMode) setPortfolioMode(saved.portfolioMode)
    setWealthApplied(true)
  }, [])

  const { data: assetsData } = useSWR<InvestmentAsset[]>(`${BASE}/api/investment-assets`, fetcher)
  const { data: wealthData } = useSWR(`${BASE}/api/wealth`, fetcher)
  const wealthKrw: number | null = wealthData?.total_wealth_krw ?? null

  // 전재산 로드 시 한 번만 자본금 초기화 (localStorage에 저장된 설정 없을 때만)
  useEffect(() => {
    if (wealthKrw && wealthKrw > 0 && !wealthApplied) {
      const snapped = Math.round(Math.min(wealthKrw, 300_000_000) / 5_000_000) * 5_000_000
      setCapital(snapped)
      setWealthApplied(true)
    }
  }, [wealthKrw, wealthApplied])

  // 설정 변경 시 localStorage 저장
  useEffect(() => {
    saveSettings(capital, riskLevel, minusLoan, creditLoan, monthlySavings, portfolioMode)
  }, [capital, riskLevel, minusLoan, creditLoan, monthlySavings])

  const leverageAmt = (minusLoan?.amount ?? 0) + (creditLoan?.amount ?? 0)
  const leverageOn = leverageAmt > 0
  const assets = assetsData ?? []
  const availableAssets = useMemo(
    () => getAvailableAssets(assets, capital, leverageOn),
    [assets, capital, leverageOn],
  )

  const stableSetCapital = useCallback((v: number) => setCapital(v), [])
  const stableSetMinusLoan = useCallback((v: MinusLoanConfig | null) => setMinusLoan(v), [])
  const stableSetCreditLoan = useCallback((v: CreditLoanConfig | null) => setCreditLoan(v), [])
  const stableSetMonthlySavings = useCallback((v: number) => setMonthlySavings(v), [])
  const stableSetRiskLevel = useCallback((v: RiskLevel) => setRiskLevel(v), [])
  const stableSetPortfolioMode = useCallback((v: PortfolioMode) => setPortfolioMode(v), [])

  return (
    <div className="space-y-4">
      <ConditionPanel
        capital={capital}
        setCapital={stableSetCapital}
        minusLoan={minusLoan}
        setMinusLoan={stableSetMinusLoan}
        creditLoan={creditLoan}
        setCreditLoan={stableSetCreditLoan}
        monthlySavings={monthlySavings}
        setMonthlySavings={stableSetMonthlySavings}
        riskLevel={riskLevel}
        setRiskLevel={stableSetRiskLevel}
        portfolioMode={portfolioMode}
        setPortfolioMode={stableSetPortfolioMode}
        wealthKrw={wealthKrw}
      />
      <AIAdvisorPanel
        capital={capital}
        minusLoan={minusLoan}
        creditLoan={creditLoan}
        monthlySavings={monthlySavings}
        riskLevel={riskLevel}
        portfolioMode={portfolioMode}
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
