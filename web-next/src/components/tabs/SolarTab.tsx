'use client'

import useSWR from 'swr'
import { fetchSolarListings } from '@/lib/api'
import type { SolarListing } from '@/types/api'

/** 출처별 배지 색상 매핑 */
const SOURCE_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  allthatsolar: { color: '#4dca7e', bg: 'rgba(77,202,126,0.15)', border: 'rgba(77,202,126,0.3)' },
  solarmarket:  { color: '#5b9bf5', bg: 'rgba(91,155,245,0.15)', border: 'rgba(91,155,245,0.3)' },
  onbid:        { color: '#e09b3d', bg: 'rgba(224,155,61,0.15)',  border: 'rgba(224,155,61,0.3)' },
}

const DEFAULT_STYLE = { color: '#9a8e84', bg: 'rgba(154,142,132,0.10)', border: 'rgba(154,142,132,0.2)' }

/** 한국식 가격 포맷 (1억 2,000만원) */
function formatKrwPrice(value: number): string {
  const eok = Math.floor(value / 100_000_000)
  const man = Math.floor((value % 100_000_000) / 10_000)

  if (eok > 0 && man > 0) return `${eok}억 ${man.toLocaleString('ko-KR')}만원`
  if (eok > 0) return `${eok}억원`
  if (man > 0) return `${man.toLocaleString('ko-KR')}만원`
  return `${value.toLocaleString('ko-KR')}원`
}

/** 오늘 날짜인지 판별 (KST 기준) */
function isToday(dateStr: string): boolean {
  const today = new Date()
  const kstOffset = 9 * 60
  const utcNow = today.getTime() + today.getTimezoneOffset() * 60_000
  const kstNow = new Date(utcNow + kstOffset * 60_000)
  const todayStr = kstNow.toISOString().slice(0, 10)
  return dateStr.slice(0, 10) === todayStr
}

/** 날짜를 간결하게 표시 */
function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const m = d.getMonth() + 1
  const day = d.getDate()
  return `${m}/${day}`
}

function SkeletonCard() {
  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2 animate-pulse">
      <div className="flex justify-between">
        <div className="space-y-1.5">
          <div className="h-3.5 w-32 bg-mc-border rounded" />
          <div className="h-2.5 w-20 bg-mc-border rounded" />
        </div>
        <div className="h-5 w-16 bg-mc-border rounded" />
      </div>
      <div className="flex gap-3">
        <div className="h-2.5 w-16 bg-mc-border rounded" />
        <div className="h-2.5 w-12 bg-mc-border rounded" />
        <div className="h-2.5 w-20 bg-mc-border rounded" />
      </div>
    </div>
  )
}

function ListingCard({ listing }: { listing: SolarListing }) {
  const style = SOURCE_STYLES[listing.source] ?? DEFAULT_STYLE
  const isNew = isToday(listing.first_seen_at)

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-3 space-y-2">
      {/* 상단: 출처 배지 + NEW 배지 */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
              style={{ color: style.color, background: style.bg, border: `1px solid ${style.border}` }}
            >
              {listing.source}
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

      {/* 중간: 지역 / 용량 / 가격 */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
        {listing.location && (
          <span>{listing.location}</span>
        )}
        {listing.capacity_kw != null && (
          <span>{listing.capacity_kw.toLocaleString('ko-KR')}kW</span>
        )}
        <span className="font-medium" style={{ color: listing.price_krw != null ? '#c9a93a' : '#9a8e84' }}>
          {listing.price_krw != null ? formatKrwPrice(listing.price_krw) : '가격 미공개'}
        </span>
      </div>

      {/* 하단: 발견일 + 원본 링크 */}
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

export function SolarTab() {
  const { data, isLoading } = useSWR('solar-listings', fetchSolarListings, {
    dedupingInterval: 300_000,
    revalidateOnFocus: false,
  })

  const listings = data?.listings ?? []

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-mono font-semibold">
          태양광 발전소 매물
        </h2>
        {data && (
          <span className="text-[10px] text-muted-foreground">
            {data.count}건
          </span>
        )}
      </div>

      {/* 로딩 */}
      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && listings.length === 0 && (
        <div className="text-center text-muted-foreground text-xs py-12">
          수집된 매물이 없습니다
        </div>
      )}

      {/* 매물 카드 리스트 (최신순) */}
      {!isLoading && listings.length > 0 && (
        <div className="space-y-2">
          {listings.map(listing => (
            <ListingCard key={`${listing.source}-${listing.listing_id}`} listing={listing} />
          ))}
        </div>
      )}
    </div>
  )
}
