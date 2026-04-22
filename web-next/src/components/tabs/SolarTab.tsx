'use client'

import { useState, useMemo, useEffect, useCallback } from 'react'
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

const DEAL_TYPE_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  '매매': { color: '#5b9bf5', bg: 'rgba(91,155,245,0.15)', border: 'rgba(91,155,245,0.3)' },
  '분양': { color: '#4dca7e', bg: 'rgba(77,202,126,0.15)', border: 'rgba(77,202,126,0.3)' },
}

const CAP_RANGES = [
  { label: '전체', min: 0, max: Infinity },
  { label: '~50kW', min: 0, max: 50 },
  { label: '50~100kW', min: 50, max: 100 },
  { label: '100~500kW', min: 100, max: 500 },
  { label: '500kW+', min: 500, max: Infinity },
]

const LS_READ    = 'solar_read_v1'
const LS_STARRED = 'solar_starred_v1'

function lsLoad(key: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(key) ?? '[]'))
  } catch {
    return new Set()
  }
}

function lsSave(key: string, set: Set<string>) {
  try {
    localStorage.setItem(key, JSON.stringify([...set]))
  } catch {}
}

function listingKey(l: SolarListing) {
  return `${l.source}-${l.listing_id}`
}

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

function ListingCard({
  listing,
  isRead,
  isStarred,
  onOpen,
  onToggleStar,
}: {
  listing: SolarListing
  isRead: boolean
  isStarred: boolean
  onOpen: () => void
  onToggleStar: (e: React.MouseEvent) => void
}) {
  const style = SOURCE_COLORS[listing.source] ?? DEFAULT_COLOR
  const isNew = isToday(listing.first_seen_at)

  function handleCardClick() {
    if (listing.url) {
      window.open(listing.url, '_blank', 'noopener,noreferrer')
      onOpen()
    }
  }

  return (
    <div
      onClick={handleCardClick}
      className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2 transition-opacity cursor-pointer hover:border-mc-border/60"
      style={{ opacity: isRead ? 0.5 : 1 }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
              style={{ color: style.color, background: style.bg, border: `1px solid ${style.border}` }}
            >
              {SOURCE_LABELS[listing.source] ?? listing.source}
            </span>
            {listing.deal_type && (() => {
              const ds = DEAL_TYPE_STYLES[listing.deal_type]
              return (
                <span
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
                  style={{ color: ds.color, background: ds.bg, border: `1px solid ${ds.border}` }}
                >
                  {listing.deal_type}
                </span>
              )
            })()}
            {isNew && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                style={{ color: '#ff6b6b', background: 'rgba(255,107,107,0.15)', border: '1px solid rgba(255,107,107,0.3)' }}
              >
                NEW
              </span>
            )}
          </div>
          <div className={`text-sm font-semibold leading-snug mt-1 line-clamp-2 ${isRead ? 'text-muted-foreground' : ''}`}>
            {listing.title ?? '(제목 없음)'}
          </div>
        </div>

        {/* 별표 버튼 */}
        <button
          onClick={onToggleStar}
          className="shrink-0 text-lg leading-none transition-transform hover:scale-110 cursor-pointer"
          style={{ color: isStarred ? '#f5a623' : 'rgba(154,142,132,0.35)' }}
          title={isStarred ? '별표 해제' : '별표'}
        >
          {isStarred ? '★' : '☆'}
        </button>
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
        {isRead && <span style={{ color: '#9a8e84' }}>열람</span>}
      </div>
    </div>
  )
}

type ViewMode = 'all' | 'unread' | 'starred'

export function SolarTab() {
  const { data, isLoading } = useSWR('solar-listings', fetchSolarListings, {
    dedupingInterval: 300_000,
    revalidateOnFocus: false,
  })

  const [readSet, setReadSet]       = useState<Set<string>>(new Set())
  const [starredSet, setStarredSet] = useState<Set<string>>(new Set())
  const [mounted, setMounted]       = useState(false)

  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set())
  const [selectedRegion, setSelectedRegion]   = useState('')
  const [capRangeIdx, setCapRangeIdx]         = useState(0)
  const [dealType, setDealType]               = useState('')
  const [viewMode, setViewMode]               = useState<ViewMode>('all')

  useEffect(() => {
    setReadSet(lsLoad(LS_READ))
    setStarredSet(lsLoad(LS_STARRED))
    setMounted(true)
  }, [])

  const markRead = useCallback((key: string) => {
    setReadSet(prev => {
      if (prev.has(key)) return prev
      const next = new Set(prev)
      next.add(key)
      lsSave(LS_READ, next)
      return next
    })
  }, [])

  const toggleStar = useCallback((key: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setStarredSet(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      lsSave(LS_STARRED, next)
      return next
    })
  }, [])

  const allListings = data?.listings ?? []

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
      const key = listingKey(l)
      if (viewMode === 'unread'  && readSet.has(key))    return false
      if (viewMode === 'starred' && !starredSet.has(key)) return false
      if (selectedSources.size > 0 && !selectedSources.has(l.source)) return false
      if (selectedRegion && regionGroup(l.location) !== selectedRegion) return false
      if (dealType && l.deal_type !== dealType) return false
      if (capRange.min > 0 || capRange.max < Infinity) {
        if (l.capacity_kw == null) return false
        if (l.capacity_kw < capRange.min || l.capacity_kw >= capRange.max) return false
      }
      return true
    })
  }, [allListings, viewMode, readSet, starredSet, selectedSources, selectedRegion, dealType, capRangeIdx])

  function toggleSource(src: string) {
    setSelectedSources(prev => {
      const next = new Set(prev)
      if (next.has(src)) next.delete(src)
      else next.add(src)
      return next
    })
  }

  const unreadCount   = mounted ? allListings.filter(l => !readSet.has(listingKey(l))).length : null
  const starredCount  = mounted ? allListings.filter(l => starredSet.has(listingKey(l))).length : null
  const hasFilter     = selectedSources.size > 0 || selectedRegion !== '' || dealType !== '' || capRangeIdx !== 0

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-mono font-semibold">태양광 발전소 매물</h2>
        {data && (
          <span className="text-[10px] text-muted-foreground">
            {hasFilter || viewMode !== 'all'
              ? `${filtered.length} / ${data.count}건`
              : `${data.count}건`}
          </span>
        )}
      </div>

      {!isLoading && allListings.length > 0 && (
        <div className="space-y-2 pb-2 border-b border-mc-border">
          {/* 보기 모드 */}
          <div className="flex gap-1">
            <FilterChip active={viewMode === 'all'}     onClick={() => setViewMode('all')}>전체</FilterChip>
            <FilterChip active={viewMode === 'unread'}  onClick={() => setViewMode('unread')}>
              미열람{unreadCount != null ? ` ${unreadCount}` : ''}
            </FilterChip>
            <FilterChip active={viewMode === 'starred'} onClick={() => setViewMode('starred')}>
              ★ 별표{starredCount ? ` ${starredCount}` : ''}
            </FilterChip>
          </div>

          {/* 거래유형 */}
          <div className="flex gap-1">
            <FilterChip active={dealType === ''}     onClick={() => setDealType('')}>전체</FilterChip>
            <FilterChip active={dealType === '매매'} onClick={() => setDealType(dealType === '매매' ? '' : '매매')}>매매</FilterChip>
            <FilterChip active={dealType === '분양'} onClick={() => setDealType(dealType === '분양' ? '' : '분양')}>분양</FilterChip>
          </div>

          {/* 출처 */}
          <div className="flex flex-wrap gap-1">
            {availableSources.map(src => (
              <FilterChip key={src} active={selectedSources.has(src)} onClick={() => toggleSource(src)}>
                {SOURCE_LABELS[src] ?? src}
              </FilterChip>
            ))}
          </div>

          {/* 지역 */}
          {availableRegions.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <FilterChip active={selectedRegion === ''} onClick={() => setSelectedRegion('')}>전체지역</FilterChip>
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

          {/* 용량 */}
          <div className="flex flex-wrap gap-1">
            {CAP_RANGES.map((range, i) => (
              <FilterChip key={range.label} active={capRangeIdx === i} onClick={() => setCapRangeIdx(i)}>
                {range.label}
              </FilterChip>
            ))}
          </div>
        </div>
      )}

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {!isLoading && allListings.length === 0 && (
        <div className="text-center text-muted-foreground text-xs py-12">
          수집된 매물이 없습니다
        </div>
      )}

      {!isLoading && allListings.length > 0 && filtered.length === 0 && (
        <div className="text-center text-muted-foreground text-xs py-8">
          조건에 맞는 매물이 없습니다
        </div>
      )}

      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map(listing => {
            const key = listingKey(listing)
            return (
              <ListingCard
                key={key}
                listing={listing}
                isRead={mounted && readSet.has(key)}
                isStarred={mounted && starredSet.has(key)}
                onOpen={() => markRead(key)}
                onToggleStar={(e) => toggleStar(key, e)}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
