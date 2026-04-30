'use client'

import { X } from 'lucide-react'
import type { CompanyProfile, Opportunity } from '@/types/api'

// -- 전략 이름 매핑 --
const STRATEGY_LABELS: Record<string, string> = {
  graham: '그레이엄',
  buffett: '버핏',
  lynch: '린치',
  momentum: '모멘텀',
  quality: '퀄리티',
  composite: '종합',
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
