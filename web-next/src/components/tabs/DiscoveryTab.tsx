'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Opportunity = {
  ticker: string
  name?: string
  sector?: string
  screen_reason?: string
  grade?: string
  composite_score?: number
  factors?: {
    quality?: number
    value?: number
    flow?: number
    momentum?: number
    growth?: number
  }
  rsi?: number
  per?: number
  pbr?: number
  roe?: number
}

const HOW_IT_WORKS = [
  { step: '1', label: 'Marcus AI가 오늘 주목할 섹터 선정', sub: '뉴스·시장 분석 기반' },
  { step: '2', label: '700개 유니버스 중 해당 섹터 필터', sub: 'KOSPI200 + S&P500' },
  { step: '3', label: '5가지 기준으로 매력도 점수 계산', sub: '수익성·가치·수급·모멘텀·성장' },
]

const FACTOR_LABELS: Record<string, string> = {
  quality: '수익성',
  value: '가치',
  flow: '수급',
  momentum: '기술',
  growth: '성장',
}

function gradeColor(grade: string | undefined): string {
  if (!grade) return '#9a8e84'
  if (grade === 'A+') return '#4dca7e'
  if (grade === 'A') return '#6dd49a'
  if (grade === 'B+') return '#c9a93a'
  if (grade === 'B') return '#e09b3d'
  return '#9a8e84'
}

function gradeBg(grade: string | undefined): string {
  if (!grade) return 'rgba(154,142,132,0.15)'
  if (grade === 'A+') return 'rgba(77,202,126,0.15)'
  if (grade === 'A') return 'rgba(109,212,154,0.12)'
  if (grade === 'B+') return 'rgba(201,169,58,0.15)'
  if (grade === 'B') return 'rgba(224,155,61,0.12)'
  return 'rgba(154,142,132,0.10)'
}

function FactorBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? '#4dca7e' : pct >= 55 ? '#c9a93a' : '#9a8e84'
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] text-muted-foreground w-7 shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-mc-border overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[9px] font-mono w-5 text-right" style={{ color }}>{pct}</span>
    </div>
  )
}

function OpportunityCard({ o }: { o: Opportunity }) {
  const score = Math.round((o.composite_score ?? 0) * 100)
  const factors = o.factors ?? {}
  const factorOrder = ['quality', 'value', 'flow', 'momentum', 'growth'] as const

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2">
      {/* 헤더: 종목명 + 등급 + 점수 */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-sm font-semibold leading-tight">{o.name ?? o.ticker}</span>
            <span className="text-[10px] text-muted-foreground font-mono">{o.ticker}</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">{o.sector ?? '—'}</div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {o.grade && (
            <span
              className="text-xs font-bold px-1.5 py-0.5 rounded"
              style={{ color: gradeColor(o.grade), background: gradeBg(o.grade) }}
            >
              {o.grade}
            </span>
          )}
          <span className="text-sm font-mono font-semibold" style={{ color: gradeColor(o.grade) }}>
            {score}
          </span>
        </div>
      </div>

      {/* 발굴 이유 */}
      {o.screen_reason && (
        <div className="text-[10px] text-muted-foreground leading-relaxed border-l-2 border-mc-border pl-2">
          {o.screen_reason}
        </div>
      )}

      {/* 세부 팩터 바 */}
      {Object.keys(factors).length > 0 && (
        <div className="space-y-0.5 pt-0.5">
          {factorOrder.map((key) => {
            const val = factors[key]
            if (val === undefined) return null
            return <FactorBar key={key} label={FACTOR_LABELS[key]} value={val} />
          })}
        </div>
      )}
    </div>
  )
}

export function DiscoveryTab() {
  const { data } = useIntelData()
  const opportunities: Opportunity[] = data?.opportunities?.opportunities ?? []

  return (
    <div className="space-y-4">
      {/* 발굴 원리 */}
      <div className="flex gap-2">
        {HOW_IT_WORKS.map(({ step, label, sub }) => (
          <div key={step} className="flex-1 rounded-md border border-mc-border bg-mc-card px-3 py-2">
            <div className="text-[10px] text-muted-foreground mb-0.5">STEP {step}</div>
            <div className="text-xs font-medium leading-snug">{label}</div>
            <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>
          </div>
        ))}
      </div>

      {/* 발굴 종목 */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-xs font-mono">
            발굴 종목
            <span className="ml-2 text-muted-foreground font-normal">
              {opportunities.length > 0 ? `${opportunities.length}개` : '없음'}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-2">
          {opportunities.length === 0 ? (
            <div className="text-center text-muted-foreground text-xs py-6">발굴 종목 없음</div>
          ) : (
            opportunities.map((o) => <OpportunityCard key={o.ticker} o={o} />)
          )}
        </CardContent>
      </Card>
    </div>
  )
}
