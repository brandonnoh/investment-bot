'use client'

import { useEffect } from 'react'
import { fmtKrw } from '@/lib/format'
import type { RiskLevel } from '@/types/advisor'

/** 자본금 슬라이더 단계 (로그 스케일 근사) */
const CAPITAL_STEPS = [
  1_000_000, 3_000_000, 5_000_000,
  10_000_000, 30_000_000, 50_000_000,
  100_000_000, 300_000_000, 500_000_000,
  1_000_000_000, 3_000_000_000, 5_000_000_000,
]

const RISK_LABELS: Record<RiskLevel, string> = {
  1: '보수',
  2: '보수-중립',
  3: '중립',
  4: '공격',
  5: '초공격',
}

/** 리스크 레벨 색상 (디자인 토큰) */
function riskLevelColor(level: RiskLevel): string {
  if (level <= 2) return 'text-mc-green'
  if (level === 3) return 'text-gold'
  return 'text-mc-red'
}

/** 자본금 포맷 (aria-valuetext용) */
function formatCapital(capital: number): string {
  return `${fmtKrw(capital)}원`
}

interface ConditionPanelProps {
  capital: number
  setCapital: (v: number) => void
  leverageOn: boolean
  setLeverageOn: (v: boolean) => void
  riskLevel: RiskLevel
  setRiskLevel: (v: RiskLevel) => void
  aiRiskLevel: RiskLevel | null
  aiRiskReason: string | null
  wealthKrw: number | null
}

export function ConditionPanel({
  capital, setCapital,
  leverageOn, setLeverageOn,
  riskLevel, setRiskLevel,
  aiRiskLevel, aiRiskReason,
  wealthKrw,
}: ConditionPanelProps) {
  /* 전재산 데이터 로드 시 초기 자본금 반영 */
  useEffect(() => {
    if (wealthKrw && wealthKrw > 0) {
      const closest = CAPITAL_STEPS.reduce((prev, curr) =>
        Math.abs(curr - wealthKrw) < Math.abs(prev - wealthKrw) ? curr : prev
      )
      setCapital(closest)
    }
  }, [wealthKrw, setCapital])

  const capitalIdx = CAPITAL_STEPS.indexOf(capital)
  const sliderIdx = capitalIdx >= 0 ? capitalIdx : 0

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-4">
      <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
        투자 조건 설정
      </h3>

      {/* 자본금 슬라이더 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="capital-slider" className="text-xs text-muted-foreground">투자 가용 자본금</label>
          <span className="text-sm font-mono font-bold text-gold">
            {formatCapital(capital)}
          </span>
        </div>
        <input
          id="capital-slider"
          type="range"
          min={0}
          max={CAPITAL_STEPS.length - 1}
          value={sliderIdx}
          onChange={e => setCapital(CAPITAL_STEPS[Number(e.target.value)])}
          aria-label="투자 가용 자본금"
          aria-valuetext={formatCapital(capital)}
          className="w-full accent-gold cursor-pointer focus-visible:outline-none focus:ring-2 focus:ring-gold"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>100만</span>
          <span>50억</span>
        </div>
      </div>

      {/* 레버리지 토글 */}
      <div className="flex items-center justify-between">
        <label className="text-xs text-muted-foreground">레버리지 활용</label>
        <button
          role="switch"
          aria-checked={leverageOn}
          aria-label="레버리지 활용"
          onClick={() => setLeverageOn(!leverageOn)}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg ${
            leverageOn ? 'bg-gold' : 'bg-mc-border'
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
              leverageOn ? 'translate-x-[18px]' : 'translate-x-[3px]'
            }`}
          />
        </button>
      </div>

      {/* 리스크 성향 슬라이더 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="risk-slider" className="text-xs text-muted-foreground">리스크 성향</label>
          <span className={`text-xs font-mono font-semibold ${riskLevelColor(riskLevel)}`}>
            Lv.{riskLevel} {RISK_LABELS[riskLevel]}
          </span>
        </div>
        <input
          id="risk-slider"
          type="range"
          min={1}
          max={5}
          value={riskLevel}
          onChange={e => setRiskLevel(Number(e.target.value) as RiskLevel)}
          aria-label="리스크 성향"
          aria-valuetext={RISK_LABELS[riskLevel]}
          className="w-full accent-gold cursor-pointer focus-visible:outline-none focus:ring-2 focus:ring-gold"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>보수</span>
          <span>공격</span>
        </div>
        {aiRiskLevel !== null && (
          <div className="mt-2 px-2.5 py-1.5 rounded bg-gold/10 border border-gold/20 text-[11px] text-gold">
            AI 추론: Lv.{aiRiskLevel} {RISK_LABELS[aiRiskLevel]}
            {aiRiskReason && <span className="text-muted-foreground ml-1">-- {aiRiskReason}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
