'use client'

import { useState } from 'react'
import { ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import { fmtKrw } from '@/lib/format'
import type { CompanyProfile, CompanyNewsItem, AnalystReport } from '@/types/api'

// -- 팩터 바 라벨 --
const FACTOR_LABELS: Record<string, string> = {
  quality: '수익',
  value: '가치',
  flow: '수급',
  momentum: '기술',
  growth: '성장',
}

// -- 국가 한국어 매핑 --
const COUNTRY_LABELS: Record<string, string> = {
  'South Korea': '한국',
  'United States': '미국',
  'Japan': '일본',
  'China': '중국',
  'Germany': '독일',
  'United Kingdom': '영국',
  'France': '프랑스',
  'Canada': '캐나다',
  'Australia': '호주',
  'Taiwan': '대만',
  'Hong Kong': '홍콩',
  'Singapore': '싱가포르',
}

// -- 산업 한국어 매핑 --
const INDUSTRY_LABELS: Record<string, string> = {
  'Aerospace & Defense': '항공우주·방산',
  'Agricultural Inputs': '농업 자재',
  'Aluminum': '알루미늄',
  'Building Materials': '건축자재',
  'Chemicals': '화학',
  'Consumer Electronics': '가전',
  'Copper': '구리',
  'Gold': '금',
  'Oil & Gas E&P': '석유·가스 탐사',
  'Oil & Gas Midstream': '석유·가스 중류',
  'Oil & Gas Refining & Marketing': '석유·가스 정제',
  'Other Industrial Metals & Mining': '기타 금속·광업',
  'Semiconductor Equipment & Materials': '반도체 장비·소재',
  'Semiconductors': '반도체',
  'Specialty Chemicals': '특수화학',
  'Steel': '철강',
  'Utilities - Regulated Electric': '전력 (규제)',
  'Utilities - Regulated Gas': '가스 (규제)',
  'Software - Application': '응용 소프트웨어',
  'Software - Infrastructure': '인프라 소프트웨어',
  'Information Technology Services': 'IT 서비스',
  'Electronic Components': '전자부품',
  'Scientific & Technical Instruments': '계측기기',
}

// -- 색상 유틸 --
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

// -- 설립일 포맷 변환 ("YYYYMMDD" → "YYYY년 M월") --
function fmtFounded(raw: string): string {
  if (raw.length < 6) return raw
  const year = raw.slice(0, 4)
  const month = parseInt(raw.slice(4, 6), 10)
  return `${year}년 ${month}월`
}

// -- 애널리스트 리포트 날짜 포맷 ("YYYYMMDD" → "YY.MM.DD") --
function fmtReportDate(raw: string): string {
  if (raw.length < 8) return raw
  return `${raw.slice(2, 4)}.${raw.slice(4, 6)}.${raw.slice(6, 8)}`
}

// -- 가격 섹션 --
export function PriceSection({ profile }: { profile: CompanyProfile }) {
  const price = profile.current_price
  const high = profile.price_52w_high
  const low = profile.price_52w_low

  if (price == null) return null

  const range = (high ?? 0) - (low ?? 0)
  const position = range > 0 ? ((price - (low ?? 0)) / range) * 100 : 50

  return (
    <div className="px-5 py-4 space-y-2">
      <div className="text-2xl font-bold font-mono">{fmtKrw(price)}</div>
      {high != null && low != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-[14px] text-muted-foreground font-mono">
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

  const hasDartInfo = profile.name_kr || profile.ceo || profile.founded || profile.address || profile.foreign_rate
  if (!profile.description && !hasDartInfo) return null

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[14px] font-mono text-muted-foreground uppercase tracking-wider">
        기업 개요
      </div>
      {profile.name_kr && (
        <div className="text-xs text-muted-foreground">{profile.name_kr}</div>
      )}
      {profile.description && (
        <>
          <p className={`text-xs leading-relaxed text-muted-foreground ${expanded ? '' : 'line-clamp-6'}`}>
            {profile.description}
          </p>
          <button
            onClick={() => setExpanded(prev => !prev)}
            className="flex items-center gap-0.5 text-[14px] transition-colors"
            style={{ color: '#4dca7e' }}
          >
            {expanded ? <><ChevronUp size={10} /> 접기</> : <><ChevronDown size={10} /> 더 보기</>}
          </button>
        </>
      )}
      <div className="flex flex-wrap gap-3 text-[14px] text-muted-foreground">
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
        {profile.employees != null && (
          <span>직원 {Number(profile.employees).toLocaleString()}명</span>
        )}
        {profile.country && <span>{COUNTRY_LABELS[profile.country] ?? profile.country}</span>}
        {profile.industry && <span>{INDUSTRY_LABELS[profile.industry] ?? profile.industry}</span>}
        {profile.ceo && <span>대표이사 {profile.ceo}</span>}
        {profile.founded && <span>설립일 {fmtFounded(profile.founded)}</span>}
        {profile.foreign_rate && <span>외국인 보유 {profile.foreign_rate}</span>}
      </div>
      {profile.address && (
        <div className="text-[14px] text-muted-foreground/70">{profile.address}</div>
      )}
    </div>
  )
}

const METRIC_TIPS: Record<string, string> = {
  PER: '주가 ÷ 주당순이익. 낮을수록 저평가. 10 이하 저평가, 30 이상 고평가 경향. 업종 평균과 비교하는 게 핵심.',
  PBR: '주가 ÷ 주당순자산. 1 미만이면 청산가치 이하로 거래 중. 낮을수록 자산 대비 저평가.',
  ROE: '자기자본으로 얼마나 이익을 버는지. 15% 이상이면 우량. 높을수록 돈을 효율적으로 굴린다는 뜻.',
  부채비율: '부채 ÷ 자기자본. 낮을수록 재무 안정. 100% 이하 안정, 200% 이상이면 부채 과다 주의.',
  매출성장: '전년 대비 매출 증가율. 높을수록 사업이 빠르게 커지고 있다는 뜻.',
  영업이익률: '매출 대비 영업이익 비율. 높을수록 본업에서 돈을 잘 번다는 뜻. 10% 이상이면 양호.',
  배당: '주가 대비 1년 배당금 비율. 2~4%가 일반적. 너무 높으면 지속 가능성 확인 필요.',
  시가총액: '회사 전체 가치 = 주가 × 총 주식 수. 대형주(10조+), 중형주(1~10조), 소형주(1조 미만).',
}

// -- 지표 그리드 --
export function MetricsGrid({ profile }: { profile: CompanyProfile }) {
  const metrics = [
    { label: 'PER', value: profile.per?.toFixed(1) },
    { label: 'PBR', value: profile.pbr?.toFixed(2) },
    { label: 'ROE', value: profile.roe != null ? `${profile.roe.toFixed(1)}%` : undefined },
    { label: '부채비율', value: profile.debt_ratio != null ? `${profile.debt_ratio.toFixed(0)}%` : undefined },
    { label: '매출성장', value: profile.revenue_growth != null ? `${profile.revenue_growth.toFixed(1)}%` : undefined },
    { label: '영업이익률', value: profile.operating_margin != null ? `${profile.operating_margin.toFixed(1)}%` : undefined },
    { label: '배당', value: profile.dividend_yield != null ? `${profile.dividend_yield.toFixed(2)}%` : undefined },
    { label: '시가총액', value: fmtMarketCap(profile.market_cap) },
  ]

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
        핵심 지표
      </div>
      <div className="grid grid-cols-2 gap-2">
        {metrics.map(m => (
          <div key={m.label} className="rounded-md bg-mc-card border border-mc-border px-3 py-2">
            <div className="text-xs text-muted-foreground">{m.label}</div>
            <div className="text-sm font-mono font-semibold mt-0.5">{m.value ?? '--'}</div>
          </div>
        ))}
      </div>
      {/* 지표 설명 영역 */}
      <div className="rounded-md bg-muted/40 border border-mc-border px-3 py-2.5 space-y-1.5">
        {metrics.filter(m => METRIC_TIPS[m.label]).map(m => (
          <div key={m.label} className="flex gap-2 text-xs leading-snug">
            <span className="text-foreground font-medium w-12 shrink-0">{m.label}</span>
            <span className="text-muted-foreground">{METRIC_TIPS[m.label]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const FACTOR_DESCS: Record<string, string> = {
  quality: 'ROE·부채비율·이익안정성 종합. 회사가 얼마나 탄탄한지.',
  value: 'PER·PBR·EV/EBITDA 종합. 현재 주가가 싼지 비싼지.',
  flow: '외국인·기관 순매수 흐름. 큰손들이 사고 있는지 팔고 있는지.',
  momentum: 'RSI·이동평균 등 기술적 추세. 지금 오르는 힘이 있는지.',
  growth: '매출·이익 성장률 종합. 사업이 얼마나 빠르게 커지고 있는지.',
}

// -- 팩터 바 --
function FactorBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? '#4dca7e' : pct >= 55 ? '#c9a93a' : '#9a8e84'
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground w-8 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-mc-border overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono w-6 text-right" style={{ color }}>{pct}</span>
    </div>
  )
}

export function FactorsSection({ factors }: { factors: Record<string, number> }) {
  const order = ['quality', 'value', 'flow', 'momentum', 'growth'] as const
  const entries = order.filter(k => factors[k] !== undefined)

  if (entries.length === 0) return null

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-3">
      <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
        팩터 점수
      </div>

      {/* 팩터 바 */}
      <div className="space-y-2">
        {entries.map(key => (
          <FactorBar key={key} label={FACTOR_LABELS[key]} value={factors[key]} />
        ))}
      </div>

      {/* 팩터 설명 영역 */}
      <div className="rounded-md bg-muted/40 border border-mc-border px-3 py-2.5 space-y-1.5">
        {entries.map(key => (
          <div key={key} className="flex gap-2 text-xs leading-snug">
            <span className="text-foreground font-medium w-8 shrink-0">{FACTOR_LABELS[key]}</span>
            <span className="text-muted-foreground">{FACTOR_DESCS[key]}</span>
          </div>
        ))}
        <p className="text-xs text-muted-foreground/60 pt-1 border-t border-mc-border mt-1">
          점수 0–100 · 70↑ <span className="text-mc-green">초록</span> · 55↑ <span className="text-amber">노랑</span> · 미만 <span className="text-muted-foreground">회색</span>
        </p>
      </div>
    </div>
  )
}

// -- 애널리스트 리포트 섹션 --
export function AnalystReportsSection({ reports }: { reports?: AnalystReport[] }) {
  if (!reports || reports.length === 0) return null

  return (
    <div className="px-5 py-3 border-t border-mc-border space-y-2">
      <div className="text-[14px] font-mono text-muted-foreground uppercase tracking-wider">
        최근 증권사 리포트
      </div>
      <div className="space-y-0">
        {reports.map((r, i) => (
          <div
            key={i}
            className={`flex items-baseline justify-between gap-2 py-1.5 ${
              i < reports.length - 1 ? 'border-b border-mc-border/50' : ''
            }`}
          >
            <div className="min-w-0 flex items-baseline gap-1.5">
              <span
                className="font-mono text-[14px] shrink-0"
                style={{ color: 'rgba(77,202,126,0.7)' }}
              >
                [{r.broker}]
              </span>
              <span className="text-xs truncate">{r.title}</span>
            </div>
            <span className="text-[14px] text-muted-foreground font-mono shrink-0">
              {fmtReportDate(r.date)}
            </span>
          </div>
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
      <div className="flex items-center gap-2 text-[14px] text-muted-foreground pl-3">
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
      <div className="text-[14px] font-mono text-muted-foreground uppercase tracking-wider">
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


