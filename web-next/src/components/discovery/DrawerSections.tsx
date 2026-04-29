'use client'

import { useState } from 'react'
import { X, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import { fmtKrw } from '@/lib/format'
import type { CompanyProfile, CompanyNewsItem, Opportunity } from '@/types/api'

// -- 전략 이름 매핑 --
const STRATEGY_LABELS: Record<string, string> = {
  graham: '그레이엄',
  buffett: '버핏',
  lynch: '린치',
  momentum: '모멘텀',
  quality: '퀄리티',
  composite: '종합',
}

// -- 팩터 바 라벨 --
const FACTOR_LABELS: Record<string, string> = {
  quality: '수익성',
  value: '가치',
  flow: '수급',
  momentum: '기술',
  growth: '성장',
}

// -- 색상 유틸 --
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

function sentimentColor(v: number | undefined): string {
  if (v === undefined) return '#9a8e84'
  if (v > 0.3) return '#4dca7e'
  if (v < -0.3) return '#ef4444'
  return '#c9a93a'
}

function relativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const mins = Math.floor(diffMs / 60000)
  if (mins < 60) return `${mins}분 전`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}시간 전`
  const days = Math.floor(hours / 24)
  return `${days}일 전`
}

function fmtMarketCap(v: number | undefined): string {
  if (v === undefined || v === null) return '--'
  const eok = v / 100_000_000
  if (eok >= 10000) return `${(eok / 10000).toFixed(1)}조`
  if (eok >= 1) return `${eok.toFixed(0)}억`
  return fmtKrw(v)
}

// -- 스켈레톤 --
export function DrawerSkeleton() {
  return (
    <div className="space-y-4 p-5 animate-pulse">
      <div className="h-5 w-32 bg-mc-border rounded" />
      <div className="h-3 w-20 bg-mc-border rounded" />
      <div className="h-8 w-24 bg-mc-border rounded mt-4" />
      <div className="h-2 w-full bg-mc-border rounded mt-2" />
      <div className="grid grid-cols-2 gap-3 mt-4">
        {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
          <div key={i} className="h-10 bg-mc-border rounded" />
        ))}
      </div>
    </div>
  )
}

// -- 가격 섹션 --
export function PriceSection({ profile }: { profile: CompanyProfile }) {
  const price = profile.current_price
  const high = profile.price_52w_high
  const low = profile.price_52w_low

  if (price === undefined) return null

  const range = (high ?? 0) - (low ?? 0)
  const position = range > 0 ? ((price - (low ?? 0)) / range) * 100 : 50

  return (
    <div className="px-5 py-4 space-y-2">
      <div className="text-2xl font-bold font-mono">{fmtKrw(price)}</div>
      {high !== undefined && low !== undefined && (
        <div className="space-y-1">
          <div className="flex justify-between text-[9px] text-muted-foreground font-mono">
            <span>52W Low {fmtKrw(low)}</span>
            <span>52W High {fmtKrw(high)}</span>
          </div>
          <div className="relative h-1.5 rounded-full bg-mc-border overflow-hidden">
            <div
              className="absolute h-full rounded-full"
              style={{
                width: `${Math.min(Math.max(position, 2), 98)}%`,
                background: 'linear-gradient(90deg, #ef4444, #c9a93a, #4dca7e)',
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// -- 기업 개요 --
export function DescriptionSection({ profile }: { profile: CompanyProfile }) {
  const [expanded, setExpanded] = useState(false)

  if (!profile.description) return null

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
        기업 개요
      </div>
      <p className={`text-xs leading-relaxed text-muted-foreground ${expanded ? '' : 'line-clamp-6'}`}>
        {profile.description}
      </p>
      {profile.description.length > 200 && (
        <button
          onClick={() => setExpanded(prev => !prev)}
          className="flex items-center gap-0.5 text-[10px] transition-colors"
          style={{ color: '#4dca7e' }}
        >
          {expanded ? <><ChevronUp size={10} /> 접기</> : <><ChevronDown size={10} /> 더 보기</>}
        </button>
      )}
      <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
        {profile.website && (
          <a
            href={profile.website}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-0.5 hover:text-foreground transition-colors"
          >
            <ExternalLink size={9} /> 웹사이트
          </a>
        )}
        {profile.employees !== undefined && (
          <span>직원 {profile.employees.toLocaleString()}명</span>
        )}
        {profile.country && <span>{profile.country}</span>}
      </div>
    </div>
  )
}

// -- 지표 그리드 --
export function MetricsGrid({ profile }: { profile: CompanyProfile }) {
  const metrics = [
    { label: 'PER', value: profile.per?.toFixed(1) },
    { label: 'PBR', value: profile.pbr?.toFixed(2) },
    { label: 'ROE', value: profile.roe !== undefined ? `${profile.roe.toFixed(1)}%` : undefined },
    { label: '부채비율', value: profile.debt_ratio !== undefined ? `${profile.debt_ratio.toFixed(0)}%` : undefined },
    { label: '매출성장', value: profile.revenue_growth !== undefined ? `${profile.revenue_growth.toFixed(1)}%` : undefined },
    { label: '영업이익률', value: profile.operating_margin !== undefined ? `${profile.operating_margin.toFixed(1)}%` : undefined },
    { label: '배당', value: profile.dividend_yield !== undefined ? `${profile.dividend_yield.toFixed(2)}%` : undefined },
    { label: '시가총액', value: fmtMarketCap(profile.market_cap) },
  ]

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
        핵심 지표
      </div>
      <div className="grid grid-cols-2 gap-2">
        {metrics.map(m => (
          <div key={m.label} className="rounded-md bg-mc-card border border-mc-border px-3 py-2">
            <div className="text-[9px] text-muted-foreground">{m.label}</div>
            <div className="text-sm font-mono font-semibold mt-0.5">{m.value ?? '--'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// -- 팩터 바 --
function FactorBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? '#4dca7e' : pct >= 55 ? '#c9a93a' : '#9a8e84'
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] text-muted-foreground w-7 shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-mc-border overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[9px] font-mono w-5 text-right" style={{ color }}>{pct}</span>
    </div>
  )
}

export function FactorsSection({ factors }: { factors: Record<string, number> }) {
  const order = ['quality', 'value', 'flow', 'momentum', 'growth'] as const
  const entries = order.filter(k => factors[k] !== undefined)

  if (entries.length === 0) return null

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
        팩터 점수
      </div>
      <div className="space-y-1">
        {entries.map(key => (
          <FactorBar key={key} label={FACTOR_LABELS[key]} value={factors[key]} />
        ))}
      </div>
    </div>
  )
}

// -- 뉴스 아이템 --
function NewsItem({ item }: { item: CompanyNewsItem }) {
  const Wrapper = item.url ? 'a' : 'div'
  const linkProps = item.url
    ? { href: item.url, target: '_blank' as const, rel: 'noopener noreferrer' }
    : {}

  return (
    <Wrapper
      {...linkProps}
      className={`block rounded-md border border-mc-border px-3 py-2 space-y-0.5 ${item.url ? 'hover:border-[#4dca7e]/40 transition-colors' : ''}`}
    >
      <div className="flex items-start gap-1.5">
        <span
          className="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
          style={{ backgroundColor: sentimentColor(item.sentiment) }}
        />
        <span className="text-xs leading-snug line-clamp-2">{item.title}</span>
      </div>
      <div className="flex items-center gap-2 text-[9px] text-muted-foreground pl-3">
        {item.source && <span>{item.source}</span>}
        {item.published_at && <span>{relativeTime(item.published_at)}</span>}
      </div>
    </Wrapper>
  )
}

export function NewsSection({ news }: { news: CompanyNewsItem[] }) {
  if (news.length === 0) return null
  const shown = news.slice(0, 5)

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
        관련 뉴스
      </div>
      <div className="space-y-1.5">
        {shown.map((item, i) => (
          <NewsItem key={i} item={item} />
        ))}
      </div>
    </div>
  )
}

// -- 프로필 없음 상태 --
export function EmptyProfileMessage() {
  return (
    <div className="px-5 py-12 text-center space-y-2">
      <div className="text-sm text-muted-foreground">프로필 준비 중</div>
      <div className="text-[10px] text-muted-foreground/70">
        다음 파이프라인 실행 후 자동 업데이트됩니다
      </div>
    </div>
  )
}

// -- 헤더 --
interface DrawerHeaderProps {
  opportunity: Opportunity | null
  profile: CompanyProfile | undefined
  onClose: () => void
}

export function DrawerHeader({ opportunity, profile, onClose }: DrawerHeaderProps) {
  const name = profile?.name ?? opportunity?.name ?? opportunity?.ticker ?? ''
  const ticker = profile?.ticker ?? opportunity?.ticker ?? ''
  const sector = profile?.sector ?? opportunity?.sector
  const grade = opportunity?.grade
  const strategies = profile?.screen_strategies ?? []

  return (
    <div className="sticky top-0 bg-mc-bg border-b border-mc-border px-5 py-4 z-10">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 space-y-1.5">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-base font-bold leading-tight">{name}</span>
            <span className="text-[10px] text-muted-foreground font-mono">{ticker}</span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {sector && (
              <span className="text-[9px] px-1.5 py-0.5 rounded border border-mc-border text-muted-foreground">
                {sector}
              </span>
            )}
            {grade && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                style={{ color: gradeColor(grade), background: gradeBg(grade) }}
              >
                {grade}
              </span>
            )}
          </div>
          {strategies.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {strategies.map(s => (
                <span
                  key={s}
                  className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                  style={{
                    background: 'rgba(77,202,126,0.08)',
                    color: '#7ddfaa',
                    border: '1px solid rgba(77,202,126,0.2)',
                  }}
                >
                  {STRATEGY_LABELS[s] ?? s}
                </span>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-mc-border transition-colors shrink-0"
          aria-label="닫기"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  )
}
