'use client'

import { useEffect } from 'react'
import { fmtKrw } from '@/lib/format'
import type { RiskLevel } from '@/types/advisor'

const STEP = 50_000_000        // 5천만원 단위
const CAPITAL_MAX = 5_000_000_000  // 50억
const LEVERAGE_MAX = 3_000_000_000  // 30억

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

function snap(v: number, step: number) { return Math.round(v / step) * step }
function fmtAmt(v: number) { return v >= 100_000_000 ? `${(v / 100_000_000).toFixed(1)}억` : `${(v / 10_000).toLocaleString()}만` }

interface ConditionPanelProps {
  capital: number
  setCapital: (v: number) => void
  leverageAmt: number
  setLeverageAmt: (v: number) => void
  riskLevel: RiskLevel
  setRiskLevel: (v: RiskLevel) => void
  aiRiskLevel: RiskLevel | null
  aiRiskReason: string | null
  wealthKrw: number | null
}

export function ConditionPanel({
  capital, setCapital,
  leverageAmt, setLeverageAmt,
  riskLevel, setRiskLevel,
  aiRiskLevel, aiRiskReason,
  wealthKrw,
}: ConditionPanelProps) {
  useEffect(() => {
    if (wealthKrw && wealthKrw > 0) setCapital(snap(Math.min(wealthKrw, CAPITAL_MAX), STEP))
  }, [wealthKrw, setCapital])

  const totalAmt = capital + leverageAmt

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-4">
      <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
        투자 조건 설정
      </h3>

      {/* 자본금 슬라이더 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="capital-slider" className="text-xs text-muted-foreground">투자 가용 자본금</label>
          <span className="text-sm font-mono font-bold text-gold">{fmtAmt(capital)}</span>
        </div>
        <input
          id="capital-slider"
          type="range"
          min={0}
          max={CAPITAL_MAX / STEP}
          step={1}
          value={capital / STEP}
          onChange={e => setCapital(Number(e.target.value) * STEP)}
          aria-label="투자 가용 자본금"
          aria-valuetext={fmtAmt(capital)}
          className="w-full accent-gold cursor-pointer focus-visible:outline-none focus:ring-2 focus:ring-gold"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>0</span><span>50억</span>
        </div>
      </div>

      {/* 레버리지 슬라이더 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="leverage-slider" className="text-xs text-muted-foreground">추가 대출금</label>
          <span className={`text-sm font-mono font-bold ${leverageAmt > 0 ? 'text-mc-red' : 'text-muted-foreground'}`}>
            {leverageAmt > 0 ? fmtAmt(leverageAmt) : '없음'}
          </span>
        </div>
        <input
          id="leverage-slider"
          type="range"
          min={0}
          max={LEVERAGE_MAX / STEP}
          step={1}
          value={leverageAmt / STEP}
          onChange={e => setLeverageAmt(Number(e.target.value) * STEP)}
          aria-label="추가 대출금"
          aria-valuetext={leverageAmt > 0 ? fmtAmt(leverageAmt) : '없음'}
          className="w-full accent-mc-red cursor-pointer focus-visible:outline-none focus:ring-2 focus:ring-mc-red"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>없음</span><span>30억</span>
        </div>
        {leverageAmt > 0 && (
          <div className="mt-1.5 text-[11px] text-muted-foreground">
            총 투자 가능금액 <span className="text-gold font-mono font-semibold">{fmtAmt(totalAmt)}</span>
            <span className="ml-1">(자본 {fmtAmt(capital)} + 대출 {fmtAmt(leverageAmt)})</span>
          </div>
        )}
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
