'use client'

import { fmtAmt } from '@/lib/format'
import type { RiskLevel, MinusLoanConfig, CreditLoanConfig, PortfolioMode } from '@/types/advisor'

const STEP = 5_000_000
const CAPITAL_MAX = 300_000_000
const LOAN_MAX = 300_000_000
const SAVINGS_MAX = 10_000_000
const SAVINGS_STEP = 500_000
const GRACE_OPTIONS = [0, 6, 12, 24] as const
const REPAY_OPTIONS = [12, 24, 36, 60, 120] as const

const RISK_LABELS: Record<RiskLevel, string> = {
  1: '보수', 2: '보수-중립', 3: '중립', 4: '공격', 5: '초공격',
}

function riskLevelColor(level: RiskLevel): string {
  if (level <= 2) return 'text-mc-green'
  if (level === 3) return 'text-gold'
  return 'text-mc-red'
}

function snap(v: number, step: number) { return Math.round(v / step) * step }

function monthlyInterest(amount: number, annualRate: number): number {
  return Math.round(amount * annualRate / 100 / 12)
}

function monthlyAnnuity(amount: number, annualRate: number, months: number): number {
  if (months <= 0 || amount <= 0) return 0
  const r = annualRate / 100 / 12
  if (r === 0) return Math.round(amount / months)
  return Math.round(amount * r / (1 - Math.pow(1 + r, -months)))
}

interface ConditionPanelProps {
  capital: number; setCapital: (v: number) => void
  minusLoan: MinusLoanConfig | null; setMinusLoan: (v: MinusLoanConfig | null) => void
  creditLoan: CreditLoanConfig | null; setCreditLoan: (v: CreditLoanConfig | null) => void
  monthlySavings: number; setMonthlySavings: (v: number) => void
  riskLevel: RiskLevel; setRiskLevel: (v: RiskLevel) => void
  portfolioMode: PortfolioMode; setPortfolioMode: (v: PortfolioMode) => void
  wealthKrw: number | null
}

const INPUT_CLS = 'w-14 text-xs text-right font-mono bg-transparent border-b border-mc-border focus:border-gold focus:outline-none px-0.5 tabular-nums'
const SELECT_CLS = 'text-[11px] bg-mc-bg border border-mc-border rounded px-1.5 py-0.5 text-foreground cursor-pointer focus:outline-none focus:border-gold'
const LOAN_TOGGLE_ON = 'bg-mc-red/10 text-mc-red border-mc-red/30 cursor-pointer'
const LOAN_TOGGLE_OFF = 'border-mc-border text-muted-foreground hover:border-mc-red/30 cursor-pointer'

export function ConditionPanel({
  capital, setCapital,
  minusLoan, setMinusLoan,
  creditLoan, setCreditLoan,
  monthlySavings, setMonthlySavings,
  riskLevel, setRiskLevel,
  portfolioMode, setPortfolioMode,
  wealthKrw,
}: ConditionPanelProps) {
  // 전재산 자동 반영은 AdvisorTab에서 처리 (중복 방지)
  void wealthKrw

  const totalLoanAmt = (minusLoan?.amount ?? 0) + (creditLoan?.amount ?? 0)
  const totalGrace = (minusLoan ? monthlyInterest(minusLoan.amount, minusLoan.rate) : 0)
    + (creditLoan ? monthlyInterest(creditLoan.amount, creditLoan.rate) : 0)
  const totalRepay = (minusLoan ? monthlyInterest(minusLoan.amount, minusLoan.rate) : 0)
    + (creditLoan ? monthlyAnnuity(creditLoan.amount, creditLoan.rate, creditLoan.repayPeriod) : 0)

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-4">
      <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
        투자 조건 설정
      </h3>

      {/* 분석 모드 */}
      <div>
        <div className="text-[10px] font-mono text-muted-foreground tracking-widest uppercase mb-1.5">분석 모드</div>
        <div className="grid grid-cols-2 rounded border border-mc-border overflow-hidden text-[10px] font-mono">
          <button
            onClick={() => setPortfolioMode('include')}
            className={`py-1.5 px-2 transition-colors text-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gold ${
              portfolioMode === 'include'
                ? 'bg-gold/10 text-gold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            포트폴리오 정리 포함
          </button>
          <button
            onClick={() => setPortfolioMode('ignore')}
            className={`py-1.5 px-2 transition-colors text-center border-l border-mc-border focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gold ${
              portfolioMode === 'ignore'
                ? 'bg-gold/10 text-gold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            신규 자본만
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1">
          {portfolioMode === 'include'
            ? '기존 종목 정리·전환 방안을 전략에 포함'
            : '입력한 자본금·대출·납입금만으로 전략 수립'}
        </p>
      </div>

      {/* 자본금 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="capital-slider" className="text-xs text-muted-foreground">투자 가용 자본금</label>
          <span className="text-sm font-mono font-bold text-gold">{fmtAmt(capital)}</span>
        </div>
        <input id="capital-slider" type="range" min={0} max={CAPITAL_MAX / STEP} step={1}
          value={capital / STEP}
          onChange={e => setCapital(snap(Number(e.target.value) * STEP, STEP))}
          className="w-full accent-gold cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>0</span><span>3억</span>
        </div>
      </div>

      {/* 월 추가 투자금 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="savings-slider" className="text-xs text-muted-foreground">월 추가 투자금 (월급 등)</label>
          <span className={`text-sm font-mono font-bold ${monthlySavings > 0 ? 'text-mc-green' : 'text-muted-foreground'}`}>
            {monthlySavings > 0 ? `+${fmtAmt(monthlySavings)}/월` : '없음'}
          </span>
        </div>
        <input id="savings-slider" type="range" min={0} max={SAVINGS_MAX / SAVINGS_STEP} step={1}
          value={monthlySavings / SAVINGS_STEP}
          onChange={e => setMonthlySavings(Number(e.target.value) * SAVINGS_STEP)}
          className="w-full accent-mc-green cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>없음</span><span>1,000만/월</span>
        </div>
      </div>

      {/* 대출 설정 */}
      <div className="space-y-2.5">
        <div className="text-[10px] font-mono text-muted-foreground tracking-widest uppercase">대출 설정</div>

        {/* 마이너스통장 */}
        <div className="rounded border border-mc-border p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium">마이너스통장</div>
              <div className="text-[10px] text-muted-foreground">이자만 납입 · 수시 상환</div>
            </div>
            <button
              onClick={() => setMinusLoan(minusLoan ? null : { amount: 50_000_000, rate: 4.5 })}
              className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${minusLoan ? LOAN_TOGGLE_ON : LOAN_TOGGLE_OFF}`}
            >
              {minusLoan ? '사용 중' : '추가'}
            </button>
          </div>

          {minusLoan && (
            <div className="space-y-2">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">금액</span>
                  <span className="text-xs font-mono text-mc-red">{fmtAmt(minusLoan.amount)}</span>
                </div>
                <input type="range" min={0} max={LOAN_MAX / STEP} step={1}
                  value={minusLoan.amount / STEP}
                  onChange={e => setMinusLoan({ ...minusLoan, amount: Number(e.target.value) * STEP })}
                  className="w-full accent-mc-red cursor-pointer"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">연이율</span>
                <div className="flex items-center gap-1">
                  <input type="number" min={0} max={30} step={0.1}
                    value={minusLoan.rate}
                    onChange={e => setMinusLoan({ ...minusLoan, rate: Number(e.target.value) })}
                    className={INPUT_CLS}
                  />
                  <span className="text-[10px] text-muted-foreground">%</span>
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground">
                월 이자 <span className="font-mono text-mc-red">{monthlyInterest(minusLoan.amount, minusLoan.rate).toLocaleString()}원</span>
              </div>
            </div>
          )}
        </div>

        {/* 신용대출 */}
        <div className="rounded border border-mc-border p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-medium">신용대출</div>
              <div className="text-[10px] text-muted-foreground">원리금 납입 · 고정금리</div>
            </div>
            <button
              onClick={() => setCreditLoan(creditLoan ? null : { amount: 30_000_000, rate: 5.5, gracePeriod: 12, repayPeriod: 36 })}
              className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${creditLoan ? LOAN_TOGGLE_ON : LOAN_TOGGLE_OFF}`}
            >
              {creditLoan ? '사용 중' : '추가'}
            </button>
          </div>

          {creditLoan && (
            <div className="space-y-2">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">금액</span>
                  <span className="text-xs font-mono text-mc-red">{fmtAmt(creditLoan.amount)}</span>
                </div>
                <input type="range" min={0} max={LOAN_MAX / STEP} step={1}
                  value={creditLoan.amount / STEP}
                  onChange={e => setCreditLoan({ ...creditLoan, amount: Number(e.target.value) * STEP })}
                  className="w-full accent-mc-red cursor-pointer"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">연이율</span>
                <div className="flex items-center gap-1">
                  <input type="number" min={0} max={30} step={0.1}
                    value={creditLoan.rate}
                    onChange={e => setCreditLoan({ ...creditLoan, rate: Number(e.target.value) })}
                    className={INPUT_CLS}
                  />
                  <span className="text-[10px] text-muted-foreground">%</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">거치기간</div>
                  <select value={creditLoan.gracePeriod}
                    onChange={e => setCreditLoan({ ...creditLoan, gracePeriod: Number(e.target.value) })}
                    className={SELECT_CLS}
                  >
                    {GRACE_OPTIONS.map(v => (
                      <option key={v} value={v}>{v === 0 ? '없음' : `${v}개월`}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">상환기간</div>
                  <select value={creditLoan.repayPeriod}
                    onChange={e => setCreditLoan({ ...creditLoan, repayPeriod: Number(e.target.value) })}
                    className={SELECT_CLS}
                  >
                    {REPAY_OPTIONS.map(v => (
                      <option key={v} value={v}>{`${v}개월`}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground">
                {creditLoan.gracePeriod > 0 && (
                  <span>거치 시 월 이자 <span className="font-mono">{monthlyInterest(creditLoan.amount, creditLoan.rate).toLocaleString()}원</span> → </span>
                )}
                상환 시 월 원리금 <span className="font-mono text-mc-red">{monthlyAnnuity(creditLoan.amount, creditLoan.rate, creditLoan.repayPeriod).toLocaleString()}원</span>
              </div>
            </div>
          )}
        </div>

        {/* 대출 요약 */}
        {(minusLoan || creditLoan) && (
          <div className="text-[11px] font-mono bg-mc-bg border border-mc-border rounded px-3 py-2 flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground">
            <span>총 대출 <span className="text-mc-red">{fmtAmt(totalLoanAmt)}</span></span>
            <span>·</span>
            <span>월 부담 <span className="text-mc-red">{totalGrace.toLocaleString()}원</span>
              {totalRepay !== totalGrace && <span className="text-muted-foreground/60"> → {totalRepay.toLocaleString()}원</span>}
            </span>
            <span>·</span>
            <span>총 투자 <span className="text-gold">{fmtAmt(capital + totalLoanAmt)}</span></span>
          </div>
        )}
      </div>

      {/* 리스크 성향 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="risk-slider" className="text-xs text-muted-foreground">리스크 성향</label>
          <span className={`text-xs font-mono font-semibold ${riskLevelColor(riskLevel)}`}>
            Lv.{riskLevel} {RISK_LABELS[riskLevel]}
          </span>
        </div>
        <input id="risk-slider" type="range" min={1} max={5}
          value={riskLevel}
          onChange={e => setRiskLevel(Number(e.target.value) as RiskLevel)}
          className="w-full accent-gold cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>보수</span><span>공격</span>
        </div>
      </div>
    </div>
  )
}
