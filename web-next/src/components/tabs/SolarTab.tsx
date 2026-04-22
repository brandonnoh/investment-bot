'use client'

import { useState, useMemo } from 'react'
import useSWR from 'swr'
import { fetchSolarListings } from '@/lib/api'
import type { SolarListing } from '@/types/api'

const SOURCE_LABELS: Record<string, string> = {
  allthatsolar: '올댓솔라',
  solarmarket: '솔라마켓',
  exchange: '발전거래소',
  solartrade: '솔라트레이드',
  solardirect: '솔라다이렉트',
  haetbit: '햇빛길',
  ssunlab: '썬랩',
  koreari: '한국재생에너지',
  onbid: '온비드',
}

const SOURCE_COLORS: Record<string, { color: string; bg: string; border: string }> = {
  solarmarket:  { color: '#5b9bf5', bg: 'rgba(91,155,245,0.15)',  border: 'rgba(91,155,245,0.3)' },
  exchange:     { color: '#4dca7e', bg: 'rgba(77,202,126,0.15)',  border: 'rgba(77,202,126,0.3)' },
  koreari:      { color: '#c97de8', bg: 'rgba(201,125,232,0.15)', border: 'rgba(201,125,232,0.3)' },
  solardirect:  { color: '#e09b3d', bg: 'rgba(224,155,61,0.15)',  border: 'rgba(224,155,61,0.3)' },
  haetbit:      { color: '#5ec8c8', bg: 'rgba(94,200,200,0.15)',  border: 'rgba(94,200,200,0.3)' },
  solartrade:   { color: '#e87070', bg: 'rgba(232,112,112,0.15)', border: 'rgba(232,112,112,0.3)' },
  ssunlab:      { color: '#a3b464', bg: 'rgba(163,180,100,0.15)', border: 'rgba(163,180,100,0.3)' },
  onbid:        { color: '#f5a623', bg: 'rgba(245,166,35,0.15)',  border: 'rgba(245,166,35,0.3)' },
  allthatsolar: { color: '#9a8e84', bg: 'rgba(154,142,132,0.10)', border: 'rgba(154,142,132,0.2)' },
}

const DEFAULT_COLOR = { color: '#9a8e84', bg: 'rgba(154,142,132,0.10)', border: 'rgba(154,142,132,0.2)' }

const CAP_RANGES = [
  { label: '전체', min: 0, max: Infinity },
  { label: '~50kW', min: 0, max: 50 },
  { label: '50~100kW', min: 50, max: 100 },
  { label: '100~500kW', min: 100, max: 500 },
  { label: '500kW+', min: 500, max: Infinity },
]

function formatKrw(value: number): string {
  const eok = Math.floor(value / 100_000_000)
  const man = Math.floor((value % 100_000_000) / 10_000)
  if (eok > 0 && man > 0) return `${eok}억 ${man.toLocaleString('ko-KR')}만원`
  if (eok > 0) return `${eok}억원`
  if (man > 0) return `${man.toLocaleString('ko-KR')}만원`
  return `${value.toLocaleString('ko-KR')}원`
}

function isToday(dateStr: string): boolean {
  const kstOffset = 9 * 60
  const utcNow = Date.now() + new Date().getTimezoneOffset() * 60_000
  const kstNow = new Date(utcNow + kstOffset * 60_000)
  return dateStr.slice(0, 10) === kstNow.toISOString().slice(0, 10)
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 지역 앞 2글자로 시/도 그룹 추출 */
function regionGroup(location: string | null): string {
  if (!location) return '지역미상'
  return location.slice(0, 2)
}

function SkeletonCard() {
  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2 animate-pulse">
      <div className="h-3.5 w-32 bg-mc-border rounded" />
      <div className="h-2.5 w-48 bg-mc-border rounded" />
      <div className="flex gap-3">
        <div className="h-2.5 w-16 bg-mc-border rounded" />
        <div className="h-2.5 w-12 bg-mc-border rounded" />
        <div className="h-2.5 w-20 bg-mc-border rounded" />
      </div>
    </div>
  )
}

function ListingCard({ listing }: { listing: SolarListing }) {
  const style = SOURCE_COLORS[listing.source] ?? DEFAULT_COLOR
  const isNew = isToday(listing.first_seen_at)

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
              style={{ color: style.color, background: style.bg, border: `1px solid ${style.border}` }}
            >
              {SOURCE_LABELS[listing.source] ?? listing.source}
            </span>
            {isNew && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                style={{ color: '#ff6b6b', background: 'rgba(255,107,107,0.15)', border: '1px solid rgba(255,107,107,0.3)' }}
              >
                NEW
              </span>
            )}
          </div>
          <div className="text-sm font-semibold leading-snug mt-1 line-clamp-2">
            {listing.title ?? '(제목 없음)'}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
        {listing.location && <span>{listing.location}</span>}
        {listing.capacity_kw != null && (
          <span>{listing.capacity_kw.toLocaleString('ko-KR')}kW</span>
        )}
        <span className="font-medium" style={{ color: listing.price_krw != null ? '#c9a93a' : '#9a8e84' }}>
          {listing.price_krw != null ? formatKrw(listing.price_krw) : '가격 미공개'}
        </span>
      </div>

      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>발견 {formatDate(listing.first_seen_at)}</span>
        {listing.url && (
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
            style={{ color: '#5b9bf5' }}
          >
            원본 보기
          </a>
        )}
      </div>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className="text-[10px] px-2 py-0.5 rounded border transition-colors cursor-pointer"
      style={
        active
          ? { color: '#5b9bf5', background: 'rgba(91,155,245,0.2)', borderColor: 'rgba(91,155,245,0.5)' }
          : { color: '#9a8e84', background: 'transparent', borderColor: 'rgba(154,142,132,0.25)' }
      }
    >
      {children}
    </button>
  )
}

export function SolarTab() {
  const { data, isLoading } = useSWR('solar-listings', fetchSolarListings, {
    dedupingInterval: 300_000,
    revalidateOnFocus: false,
  })

  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set())
  const [selectedRegion, setSelectedRegion] = useState<string>('')
  const [capRangeIdx, setCapRangeIdx] = useState(0)

  const allListings = data?.listings ?? []

  // 필터용 집계
  const availableSources = useMemo(
    () => [...new Set(allListings.map(l => l.source))].sort(),
    [allListings],
  )

  const availableRegions = useMemo(() => {
    const groups = [...new Set(allListings.map(l => regionGroup(l.location)))]
    return groups.filter(g => g !== '지역미상').sort()
  }, [allListings])

  const filtered = useMemo(() => {
    const capRange = CAP_RANGES[capRangeIdx]
    return allListings.filter(l => {
      if (selectedSources.size > 0 && !selectedSources.has(l.source)) return false
      if (selectedRegion && regionGroup(l.location) !== selectedRegion) return false
      if (capRange.min > 0 || capRange.max < Infinity) {
        if (l.capacity_kw == null) return false
        if (l.capacity_kw < capRange.min || l.capacity_kw >= capRange.max) return false
      }
      return true
    })
  }, [allListings, selectedSources, selectedRegion, capRangeIdx])

  function toggleSource(src: string) {
    setSelectedSources(prev => {
      const next = new Set(prev)
      if (next.has(src)) next.delete(src)
      else next.add(src)
      return next
    })
  }

  const hasFilter = selectedSources.size > 0 || selectedRegion !== '' || capRangeIdx !== 0

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-mono font-semibold">태양광 발전소 매물</h2>
        {data && (
          <span className="text-[10px] text-muted-foreground">
            {hasFilter ? `${filtered.length} / ${data.count}건` : `${data.count}건`}
          </span>
        )}
      </div>

      {/* 필터 패널 */}
      {!isLoading && allListings.length > 0 && (
        <div className="space-y-2 pb-2 border-b border-mc-border">
          {/* 출처 필터 */}
          <div className="flex flex-wrap gap-1">
            {availableSources.map(src => (
              <FilterChip
                key={src}
                active={selectedSources.has(src)}
                onClick={() => toggleSource(src)}
              >
                {SOURCE_LABELS[src] ?? src}
              </FilterChip>
            ))}
          </div>

          {/* 지역 필터 */}
          {availableRegions.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <FilterChip active={selectedRegion === ''} onClick={() => setSelectedRegion('')}>
                전체지역
              </FilterChip>
              {availableRegions.map(r => (
                <FilterChip
                  key={r}
                  active={selectedRegion === r}
                  onClick={() => setSelectedRegion(r === selectedRegion ? '' : r)}
                >
                  {r}
                </FilterChip>
              ))}
            </div>
          )}

          {/* 용량 필터 */}
          <div className="flex flex-wrap gap-1">
            {CAP_RANGES.map((range, i) => (
              <FilterChip key={range.label} active={capRangeIdx === i} onClick={() => setCapRangeIdx(i)}>
                {range.label}
              </FilterChip>
            ))}
          </div>
        </div>
      )}

      {/* 로딩 */}
      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && allListings.length === 0 && (
        <div className="text-center text-muted-foreground text-xs py-12">
          수집된 매물이 없습니다
        </div>
      )}

      {/* 필터 결과 없음 */}
      {!isLoading && allListings.length > 0 && filtered.length === 0 && (
        <div className="text-center text-muted-foreground text-xs py-8">
          조건에 맞는 매물이 없습니다
        </div>
      )}

      {/* 매물 카드 리스트 */}
      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map(listing => (
            <ListingCard key={`${listing.source}-${listing.listing_id}`} listing={listing} />
          ))}
        </div>
      )}
    </div>
  )
}
