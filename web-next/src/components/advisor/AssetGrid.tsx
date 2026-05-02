'use client'

import { useState, useMemo } from 'react'
import { CheckCircle2, XCircle, AlertTriangle, Clock } from 'lucide-react'
import { fmtKrw } from '@/lib/format'
import type {
  InvestmentAsset,
  AssetCategory,
  AccessStatus,
  SortOption,
} from '@/types/advisor'

/** 카테고리 필터 목록 */
const CATEGORY_FILTERS: { key: AssetCategory | 'all'; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'finance', label: '전통금융' },
  { key: 'realestate', label: '부동산' },
  { key: 'derivatives', label: '파생상품' },
  { key: 'alternative', label: '대체투자' },
  { key: 'private', label: '사모/전문' },
  { key: 'energy', label: '에너지' },
  { key: 'crowd', label: '크라우드펀딩' },
]

const SORT_OPTIONS: { key: SortOption; label: string }[] = [
  { key: 'return', label: '수익률' },
  { key: 'risk', label: '리스크' },
  { key: 'capital', label: '최소자본' },
]

/** 유동성 레이블 */
const LIQUIDITY_LABEL: Record<string, string> = {
  instant: '즉시',
  days: '수일',
  weeks: '수주',
  months: '수개월',
  years: '수년',
}

interface AssetGridProps {
  assets: InvestmentAsset[]
  capital: number
  leverageOn: boolean
}

/** 자산 접근성 판정 */
function getAccessStatus(
  asset: InvestmentAsset,
  capital: number,
  leverageOn: boolean,
): AccessStatus {
  if (asset.status === 'upcoming') return 'upcoming'

  const minRequired = leverageOn && asset.min_capital_leveraged !== null
    ? asset.min_capital_leveraged
    : asset.min_capital

  const capitalOk = minRequired <= capital

  if (capitalOk && asset.regulation_note) return 'conditional'
  if (capitalOk) return 'available'
  return 'insufficient'
}

/** 정렬 비교 함수 */
function sortAssets(assets: InvestmentAsset[], sort: SortOption, dir: 'asc' | 'desc'): InvestmentAsset[] {
  const sorted = [...assets]
  const d = dir === 'asc' ? 1 : -1
  switch (sort) {
    case 'return':
      sorted.sort((a, b) => d * (a.expected_return_max - b.expected_return_max))
      break
    case 'risk':
      sorted.sort((a, b) => d * (a.risk_level - b.risk_level))
      break
    case 'capital':
      sorted.sort((a, b) => d * (a.min_capital - b.min_capital))
      break
  }
  return sorted
}

/** 정렬 기준별 기본 방향 */
const DEFAULT_DIR: Record<SortOption, 'asc' | 'desc'> = {
  return: 'desc',
  risk: 'asc',
  capital: 'asc',
}

export function AssetGrid({ assets, capital, leverageOn }: AssetGridProps) {
  const [category, setCategory] = useState<AssetCategory | 'all'>('all')
  const [sort, setSort] = useState<SortOption>('return')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(DEFAULT_DIR['return'])

  function handleSort(key: SortOption) {
    if (key === sort) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSort(key)
      setSortDir(DEFAULT_DIR[key])
    }
  }

  const filtered = useMemo(() => {
    let result = assets
    if (category !== 'all') {
      result = result.filter(a => a.category === category)
    }
    return sortAssets(result, sort, sortDir)
  }, [assets, category, sort, sortDir])

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-3">
      <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
        투자 자산 목록 <span className="text-foreground">{filtered.length}</span>
      </h3>

      {/* 카테고리 필터 칩 */}
      <div className="flex flex-wrap gap-1.5">
        {CATEGORY_FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setCategory(f.key)}
            aria-pressed={category === f.key}
            className={`px-2.5 py-2 text-[14px] rounded-full border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg ${
              category === f.key
                ? 'bg-gold/20 border-gold/40 text-gold'
                : 'bg-transparent border-mc-border text-muted-foreground hover:text-foreground'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* 정렬 */}
      <div className="flex items-center gap-2">
        <span className="text-[14px] text-muted-foreground">정렬:</span>
        {SORT_OPTIONS.map(s => {
          const active = sort === s.key
          const arrow = active ? (sortDir === 'desc' ? '↓' : '↑') : (DEFAULT_DIR[s.key] === 'desc' ? '↓' : '↑')
          return (
            <button
              key={s.key}
              onClick={() => handleSort(s.key)}
              aria-pressed={active}
              className={`text-[14px] px-2 py-1.5 rounded transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg ${
                active
                  ? 'text-gold underline underline-offset-2'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {s.label}{arrow}
            </button>
          )
        })}
      </div>

      {/* 자산 카드 그리드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map(asset => (
          <AssetCard
            key={asset.id}
            asset={asset}
            status={getAccessStatus(asset, capital, leverageOn)}
            leverageOn={leverageOn}
          />
        ))}
      </div>
    </div>
  )
}

/* ─── 자산 카드 ─── */

const STATUS_CONFIG: Record<AccessStatus, { icon: React.ReactNode; label: string; color: string; border: string }> = {
  available:    { icon: <CheckCircle2 size={12} />,   label: '가능',     color: 'text-mc-green',          border: 'border-mc-green/30' },
  insufficient: { icon: <XCircle size={12} />,        label: '자본부족', color: 'text-mc-red',            border: 'border-mc-red/30' },
  conditional:  { icon: <AlertTriangle size={12} />,  label: '조건부',   color: 'text-gold',              border: 'border-gold/30' },
  upcoming:     { icon: <Clock size={12} />,          label: '출시예정', color: 'text-muted-foreground',  border: 'border-mc-border' },
}

function AssetCard({
  asset, status, leverageOn,
}: {
  asset: InvestmentAsset
  status: AccessStatus
  leverageOn: boolean
}) {
  const cfg = STATUS_CONFIG[status]
  const minCapitalDisplay = leverageOn && asset.min_capital_leveraged !== null
    ? asset.min_capital_leveraged
    : asset.min_capital

  return (
    <div className={`rounded-md border bg-mc-bg p-3 space-y-2 ${cfg.border}`}>
      {/* 헤더: 상태 + 이름 */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate">{asset.name}</div>
          <div className="text-[14px] text-muted-foreground">{asset.description}</div>
        </div>
        <span className={`shrink-0 inline-flex items-center gap-1 text-[14px] px-1.5 py-0.5 rounded border font-mono ${cfg.color} ${cfg.border} bg-transparent`}>
          {cfg.icon} {cfg.label}
        </span>
      </div>

      {/* 수치 정보 */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[14px]">
        <div>
          <span className="text-muted-foreground">최소자본 </span>
          <span className="font-mono">{fmtKrw(minCapitalDisplay)}원</span>
        </div>
        <div>
          <span className="text-muted-foreground">기대수익 </span>
          <span className={`font-mono ${returnColor(asset.expected_return_max)}`}>
            {asset.expected_return_min}~{asset.expected_return_max}%
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">리스크 </span>
          <span className={riskColor(asset.risk_level)}>
            {riskStars(asset.risk_level)}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">유동성 </span>
          <span className="font-mono">{LIQUIDITY_LABEL[asset.liquidity]}</span>
        </div>
      </div>

      {/* 뱃지 영역 */}
      <div className="flex flex-wrap gap-1">
        {asset.leverage_available && asset.leverage_type && (
          <span className="text-[14px] px-1.5 py-0.5 rounded bg-gold/10 text-gold/80 border border-gold/20">
            {asset.leverage_type}
          </span>
        )}
        {asset.tax_benefit && (
          <span className="text-[14px] px-1.5 py-0.5 rounded bg-mc-green/10 text-mc-green/80 border border-mc-green/20">
            {asset.tax_benefit}
          </span>
        )}
        {asset.regulation_note && (
          <span className="text-[14px] px-1.5 py-0.5 rounded bg-mc-red/10 text-mc-red/80 border border-mc-red/20">
            {asset.regulation_note}
          </span>
        )}
        {asset.beginner_friendly && (
          <span className="text-[14px] px-1.5 py-0.5 rounded bg-gold/15 text-gold border border-gold/30">
            초보 OK
          </span>
        )}
        {asset.status === 'upcoming' && asset.upcoming_date && (
          <span className="text-[14px] px-1.5 py-0.5 rounded bg-mc-border/20 text-muted-foreground border border-mc-border">
            {asset.upcoming_date} 예정
          </span>
        )}
      </div>

      {/* 주의사항 */}
      {asset.caution && (
        <div className="text-[14px] text-mc-red/80 bg-mc-red/5 rounded px-2 py-1">
          {asset.caution}
        </div>
      )}
    </div>
  )
}

/* ─── 유틸 ─── */

function riskStars(level: number): string {
  return '★'.repeat(level) + '☆'.repeat(5 - level)
}

function riskColor(level: number): string {
  if (level <= 2) return 'text-mc-green'
  if (level === 3) return 'text-gold'
  return 'text-mc-red'
}

function returnColor(max: number): string {
  if (max >= 30) return 'text-mc-green'
  if (max >= 10) return 'text-gold'
  return 'text-foreground'
}
