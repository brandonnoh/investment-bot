'use client'

import { useEffect, useCallback } from 'react'
import useSWR from 'swr'
import { fetchCompanyProfile } from '@/lib/api'
import type { CompanyProfile, Opportunity } from '@/types/api'
import {
  DrawerHeader,
  DrawerSkeleton,
  PriceSection,
  DescriptionSection,
  MetricsGrid,
  FactorsSection,
  NewsSection,
  EmptyProfileMessage,
} from './DrawerSections'

// -- 프로필이 비어있는지 확인 --
function isEmptyProfile(p: CompanyProfile | undefined): boolean {
  if (!p) return true
  return Object.keys(p).length === 0
}

// -- 메인 드로어 --
export interface CompanyDrawerProps {
  ticker: string | null
  opportunity: Opportunity | null
  onClose: () => void
}

export function CompanyDrawer({ ticker, opportunity, onClose }: CompanyDrawerProps) {
  const isOpen = ticker !== null

  const { data: profile, isLoading } = useSWR(
    ticker ? `company-${ticker}` : null,
    () => fetchCompanyProfile(ticker ?? ''),
    { revalidateOnFocus: false }
  )

  // ESC 키로 닫기
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen) return null

  const empty = !isLoading && isEmptyProfile(profile)
  const factors = opportunity?.factors ?? {}

  return (
    <>
      {/* 배경 오버레이 */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* 슬라이드인 패널 */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-md bg-mc-bg border-l border-mc-border z-50 overflow-y-auto transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <DrawerHeader
          opportunity={opportunity}
          profile={profile}
          onClose={onClose}
        />

        {isLoading && <DrawerSkeleton />}

        {empty && <EmptyProfileMessage />}

        {!isLoading && !empty && profile && (
          <>
            <PriceSection profile={profile} />
            <DescriptionSection profile={profile} />
            <MetricsGrid profile={profile} />
            {Object.keys(factors).length > 0 && (
              <FactorsSection factors={factors} />
            )}
            {profile.recent_news && profile.recent_news.length > 0 && (
              <NewsSection news={profile.recent_news} />
            )}
            {/* 하단 여백 */}
            <div className="h-8" />
          </>
        )}
      </div>
    </>
  )
}
