'use client'

import { useState, useMemo } from 'react'
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
function sortAssets(assets: InvestmentAsset[], sort: SortOption): InvestmentAsset[] {
  const sorted = [...assets]
  switch (sort) {
    case 'return':
      sorted.sort((a, b) => b.expected_return_max - a.expected_return_max)
      break
    case 'risk':
      sorted.sort((a, b) => a.risk_level - b.risk_level)
      break
    case 'capital':
      sorted.sort((a, b) => a.min_capital - b.min_capital)
      break
  }
  return sorted
}

export function AssetGrid({ assets, capital, leverageOn }: AssetGridProps) {
  const [category, setCategory] = useState<AssetCategory | 'all'>('all')
  const [sort, setSort] = useState<SortOption>('return')

  const filtered = useMemo(() => {
    let result = assets
    if (category !== 'all') {
      result = result.filter(a => a.category === category)
    }
    return sortAssets(result, sort)
  }, [assets, category, sort])

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
            className={`px-2.5 py-1 text-[11px] rounded-full border transition-colors cursor-pointer ${
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
        <span className="text-[10px] text-muted-foreground">정렬:</span>
        {SORT_OPTIONS.map(s => (
          <button
            key={s.key}
            onClick={() => setSort(s.key)}
            className={`text-[10px] px-2 py-0.5 rounded transition-colors cursor-pointer ${
              sort === s.key
                ? 'text-gold underline underline-offset-2'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {s.label}{s.key === 'return' ? '↓' : '↑'}
          </button>
        ))}
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

const STATUS_CONFIG: Record<AccessStatus, { icon: string; label: string; color: string; border: string }> = {
  available:    { icon: '✓', label: '가능',     color: 'text-[#4dca7e]', border: 'border-[#4dca7e]/30' },
  insufficient: { icon: '✗', label: '자본부족', color: 'text-[#e05252]', border: 'border-[#e05252]/30' },
  conditional:  { icon: '△', label: '조건부',   color: 'text-[#c9a93a]', border: 'border-[#c9a93a]/30' },
  upcoming:     { icon: '🔜', label: '출시예정', color: 'text-muted-foreground', border: 'border-mc-border' },
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
          <div className="text-[10px] text-muted-foreground">{asset.description}</div>
        </div>
        <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border font-mono ${cfg.color} ${cfg.border} bg-transparent`}>
          {cfg.icon} {cfg.label}
        </span>
      </div>

      {/* 수치 정보 */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
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
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20">
            {asset.leverage_type}
          </span>
        )}
        {asset.tax_benefit && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-300 border border-green-500/20">
            {asset.tax_benefit}
          </span>
        )}
        {asset.regulation_note && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
            {asset.regulation_note}
          </span>
        )}
        {asset.beginner_friendly && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
            초보 OK
          </span>
        )}
        {asset.status === 'upcoming' && asset.upcoming_date && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-500/10 text-gray-400 border border-gray-500/20">
            {asset.upcoming_date} 예정
          </span>
        )}
      </div>

      {/* 주의사항 */}
      {asset.caution && (
        <div className="text-[10px] text-[#e05252]/80 bg-[#e05252]/5 rounded px-2 py-1">
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
  if (level <= 2) return 'text-[#4dca7e]'
  if (level === 3) return 'text-[#c9a93a]'
  return 'text-[#e05252]'
}

function returnColor(max: number): string {
  if (max >= 30) return 'text-[#4dca7e]'
  if (max >= 10) return 'text-[#c9a93a]'
  return 'text-foreground'
}
