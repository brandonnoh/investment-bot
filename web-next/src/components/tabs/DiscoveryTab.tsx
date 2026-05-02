'use client'

import { useState, useEffect } from 'react'
import { Search, X } from 'lucide-react'
import { useIntelData } from '@/hooks/useIntelData'
import { useOpportunities, STRATEGIES, type StrategyId } from '@/hooks/useOpportunities'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useMCStore } from '@/store/useMCStore'
import { CompanyDrawer } from '@/components/discovery/CompanyDrawer'
import type { Opportunity } from '@/types/api'

const HOW_IT_WORKS = [
  { step: '1', label: 'Marcus AI가 오늘 주목할 섹터 선정', sub: '뉴스·시장 분석 기반' },
  { step: '2', label: '700개 유니버스 중 해당 섹터 필터', sub: 'KOSPI200 + S&P500' },
  { step: '3', label: '선택한 거장의 기준으로 종목 발굴', sub: '렌즈를 바꿔 다른 시각으로' },
]

const FACTOR_LABELS: Record<string, string> = {
  quality: '수익',
  value: '가치',
  flow: '수급',
  momentum: '기술',
  growth: '성장',
}

const SECTOR_LABELS: Record<string, string> = {
  'Basic Materials': '소재',
  'Communication Services': '통신서비스',
  'Consumer Cyclical': '경기소비재',
  'Consumer Defensive': '필수소비재',
  'Energy': '에너지',
  'Financial Services': '금융',
  'Healthcare': '헬스케어',
  'Industrials': '산업재',
  'Real Estate': '부동산',
  'Technology': '기술',
  'Utilities': '유틸리티',
}

function isKrTicker(ticker: string) {
  return ticker.endsWith('.KS') || ticker.endsWith('.KQ')
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
      <span className="text-[14px] text-muted-foreground w-8 shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-mc-border overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[14px] font-mono w-5 text-right" style={{ color }}>{pct}</span>
    </div>
  )
}


function SkeletonCard() {
  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2 animate-pulse">
      <div className="flex justify-between">
        <div className="space-y-1.5"><div className="h-3.5 w-24 bg-mc-border rounded" /><div className="h-2.5 w-16 bg-mc-border rounded" /></div>
        <div className="h-6 w-12 bg-mc-border rounded" />
      </div>
      <div className="h-2 w-full bg-mc-border rounded" />
      <div className="space-y-1">{[1,2,3,4,5].map(i => <div key={i} className="h-1.5 w-full bg-mc-border rounded" />)}</div>
    </div>
  )
}

function OpportunityCard({ o, highlighted, id, onClick }: { o: Opportunity; highlighted: boolean; id?: string; onClick?: () => void }) {
  const score = Math.round((o.composite_score ?? 0) * 100)
  const factors = o.factors ?? {}
  const factorOrder = ['quality', 'value', 'flow', 'momentum', 'growth'] as const

  return (
    <div
      id={id}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick?.() }}
      className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2 transition-all cursor-pointer hover:border-[#4dca7e]/40"
      style={highlighted ? { borderColor: '#4dca7e', boxShadow: '0 0 0 1px #4dca7e' } : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-sm font-semibold leading-tight">{o.name ?? o.ticker}</span>
            <span className="text-[14px] text-muted-foreground font-mono">{o.ticker}</span>
          </div>
          <div className="text-[14px] text-muted-foreground mt-0.5">{o.sector ? (SECTOR_LABELS[o.sector] ?? o.sector) : '—'}</div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {o.grade && (
            <span className="text-xs font-bold px-1.5 py-0.5 rounded"
              style={{ color: gradeColor(o.grade), background: gradeBg(o.grade) }}>
              {o.grade}
            </span>
          )}
          <span className="text-sm font-mono font-semibold" style={{ color: gradeColor(o.grade) }}>
            {score}
          </span>
        </div>
      </div>

      {o.screen_reason && (
        <div className="text-[14px] text-muted-foreground leading-relaxed border-l-2 border-mc-border pl-2">
          {o.screen_reason}
        </div>
      )}

      {Object.keys(factors).length > 0 && (
        <div className="space-y-0.5 pt-0.5">
          {factorOrder.map((key) => {
            const val = (factors as Record<string, number>)[key]
            if (val === undefined) return null
            return <FactorBar key={key} label={FACTOR_LABELS[key]} value={val} />
          })}
        </div>
      )}
    </div>
  )
}

function MarketList({ opportunities, isLoading, emptyLabel, marcusPickedTicker, onSelect }: {
  opportunities: Opportunity[]; isLoading: boolean; emptyLabel: string; marcusPickedTicker: string | null; onSelect: (o: Opportunity) => void
}) {
  if (isLoading) {
    return <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-2">{[1,2,3].map(i => <SkeletonCard key={i} />)}</div>
  }
  if (opportunities.length === 0) {
    return <div className="text-center text-muted-foreground text-xs py-8">{emptyLabel}</div>
  }
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-2">
      {opportunities.map((o) => {
        const highlighted = !!marcusPickedTicker &&
          (o.ticker === marcusPickedTicker || o.ticker.startsWith(marcusPickedTicker))
        return <OpportunityCard key={o.ticker} o={o} highlighted={highlighted} id={`opp-${o.ticker}`} onClick={() => onSelect(o)} />
      })}
    </div>
  )
}

type DiscoveryProps = { market: 'kr' | 'us'; search: string; marcusPickedTicker: string | null; onSelect: (o: Opportunity) => void }

function applyFilter(list: Opportunity[], market: 'kr' | 'us', search: string) {
  const byMarket = list.filter(o => market === 'kr' ? isKrTicker(o.ticker) : !isKrTicker(o.ticker))
  if (!search) return byMarket
  const q = search.toLowerCase()
  return byMarket.filter(o => o.ticker.toLowerCase().includes(q) || (o.name ?? '').toLowerCase().includes(q))
}

// composite 전략은 기존 useIntelData에서 가져오는 래퍼
function CompositeDiscovery({ market, search, marcusPickedTicker, onSelect }: DiscoveryProps) {
  const { data, isLoading } = useIntelData()
  const all: Opportunity[] = data?.opportunities?.opportunities ?? []
  return (
    <MarketList
      opportunities={applyFilter(all, market, search)}
      isLoading={isLoading}
      emptyLabel={`발굴된 ${market === 'kr' ? '국내' : '미국'} 종목 없음`}
      marcusPickedTicker={marcusPickedTicker}
      onSelect={onSelect}
    />
  )
}

function StrategyDiscovery({ strategy, market, search, marcusPickedTicker, onSelect }: DiscoveryProps & { strategy: StrategyId }) {
  const { opportunities, isLoading } = useOpportunities(strategy)
  return (
    <MarketList
      opportunities={applyFilter(opportunities, market, search)}
      isLoading={isLoading}
      emptyLabel={`이 렌즈로 발굴된 ${market === 'kr' ? '국내' : '미국'} 종목 없음`}
      marcusPickedTicker={marcusPickedTicker}
      onSelect={onSelect}
    />
  )
}

export function DiscoveryTab() {
  const [strategy, setStrategy] = useState<StrategyId>('composite')
  const [market, setMarket] = useState<'kr' | 'us'>('kr')
  const [search, setSearch] = useState<string>('')
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null)

  const { marcusPickedTicker, setMarcusPickedTicker } = useMCStore()
  const { data: intelData } = useIntelData()

  // Marcus에서 진입 시 search 자동 반영 + 카드 스크롤
  useEffect(() => {
    if (!marcusPickedTicker) return
    setSearch(marcusPickedTicker)
    // 필터링 후 카드가 렌더될 때까지 한 프레임 대기
    requestAnimationFrame(() => {
      const el = document.getElementById(`opp-${marcusPickedTicker}`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }, [marcusPickedTicker])

  const currentMeta = STRATEGIES.find(s => s.id === strategy)

  const opportunitiesUpdatedAt = (() => {
    const ts = intelData?.opportunities?.updated_at
    if (!ts) return null
    try {
      return new Date(ts).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch { return null }
  })()

  function handleStrategyChange(id: StrategyId) {
    setStrategy(id)
    setMarcusPickedTicker(null)
    setSearch('')
  }

  return (
    <div className="space-y-4">
      {/* 발굴 원리 */}
      <div className="flex gap-2">
        {HOW_IT_WORKS.map(({ step, label, sub }) => (
          <div key={step} className="flex-1 rounded-md border border-mc-border bg-mc-card px-3 py-2">
            <div className="text-[14px] text-muted-foreground mb-0.5">STEP {step}</div>
            <div className="text-xs font-medium leading-snug">{label}</div>
            <div className="text-[14px] text-muted-foreground mt-0.5">{sub}</div>
          </div>
        ))}
      </div>

      {/* 렌즈 선택 칩 */}
      <div className="space-y-1.5">
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 no-scrollbar">
          {STRATEGIES.map(s => {
            const active = strategy === s.id
            return (
              <button
                key={s.id}
                onClick={() => handleStrategyChange(s.id)}
                className="shrink-0 text-[14px] font-medium px-3 py-1 rounded-full border transition-colors"
                style={{
                  borderColor: active ? '#4dca7e' : '#2a2420',
                  background: active ? 'rgba(77,202,126,0.15)' : 'transparent',
                  color: active ? '#4dca7e' : '#9a8e84',
                }}
              >
                {s.name}
              </button>
            )
          })}
        </div>
        {/* 현재 렌즈 설명 + 조건 배지 */}
        {currentMeta && (
          <div className="space-y-1.5 px-0.5">
            <div className="text-[14px] text-muted-foreground">
              <span className="font-medium" style={{ color: '#4dca7e' }}>{currentMeta.name} 렌즈</span>
              {' — '}{currentMeta.description}
            </div>
            <div className="flex flex-wrap gap-1">
              {'criteria' in currentMeta && (currentMeta.criteria as readonly string[]).map((c) => (
                <span
                  key={c}
                  className="text-[14px] font-mono px-1.5 py-0.5 rounded"
                  style={{ background: 'rgba(77,202,126,0.08)', color: '#7ddfaa', border: '1px solid rgba(77,202,126,0.2)' }}
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 검색창 */}
      <div className="relative group">
        <Search
          size={13}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-[#4dca7e] transition-colors pointer-events-none"
        />
        <input
          type="text"
          placeholder="종목명 또는 ticker..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            if (!e.target.value) setMarcusPickedTicker(null)
          }}
          className="w-full text-xs pl-8 pr-8 py-2 rounded-md border border-mc-border bg-mc-card placeholder:text-muted-foreground/50 focus:outline-none focus:border-[#4dca7e] transition-colors"
        />
        {search && (
          <button
            onClick={() => { setSearch(''); setMarcusPickedTicker(null) }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={12} />
          </button>
        )}
        {marcusPickedTicker && search === marcusPickedTicker && (
          <span className="absolute right-7 top-1/2 -translate-y-1/2 text-[14px] font-medium px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(77,202,126,0.12)', color: '#4dca7e' }}>
            마커스
          </span>
        )}
      </div>

      {/* 국장 / 미장 탭 + 결과 */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-3 px-4 pb-0">
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <CardTitle className="text-xs font-mono">발굴 종목</CardTitle>
              {opportunitiesUpdatedAt && (
                <span className="text-[14px] text-muted-foreground">{opportunitiesUpdatedAt} 기준</span>
              )}
            </div>
            <div className="flex rounded-md border border-mc-border overflow-hidden text-[14px] font-medium">
              {(['kr', 'us'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMarket(m)}
                  className="px-3 py-1 transition-colors"
                  style={{
                    background: market === m ? 'rgba(77,202,126,0.15)' : 'transparent',
                    color: market === m ? '#4dca7e' : '#9a8e84',
                    borderLeft: m === 'us' ? '1px solid #2a2420' : undefined,
                  }}
                >
                  {m === 'kr' ? '국장' : '미장'}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-3">
          {strategy === 'composite'
            ? <CompositeDiscovery market={market} search={search} marcusPickedTicker={marcusPickedTicker} onSelect={setSelectedOpp} />
            : <StrategyDiscovery strategy={strategy} market={market} search={search} marcusPickedTicker={marcusPickedTicker} onSelect={setSelectedOpp} />
          }
        </CardContent>
      </Card>

      <CompanyDrawer
        ticker={selectedOpp?.ticker ?? null}
        opportunity={selectedOpp}
        onClose={() => setSelectedOpp(null)}
      />
    </div>
  )
}
