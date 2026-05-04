'use client'

import { useState } from 'react'
import useSWR from 'swr'
import type { HealthCheckData, HealthCheckItem } from '@/types/api'

const CATEGORY_LABELS: Record<string, string> = {
  service: '서비스',
  pipeline: '데이터 파이프라인',
  cron: '크론 잡',
  report: 'AI 리포트',
  database: 'DB 테이블',
  intel: 'Intel 파일',
  other: '기타',
}

const CATEGORY_ORDER = ['service', 'pipeline', 'cron', 'report', 'database', 'intel', 'other']

async function fetchHealth(): Promise<HealthCheckData> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error('health fetch failed')
  return res.json()
}

function StatusBadge({ status }: { status: HealthCheckItem['status'] }) {
  const styles = {
    ok:   { color: '#4dca7e', bg: 'rgba(77,202,126,0.12)', label: 'OK' },
    warn: { color: '#e09b3d', bg: 'rgba(224,155,61,0.12)', label: 'WARN' },
    fail: { color: '#e05656', bg: 'rgba(224,86,86,0.12)',  label: 'FAIL' },
  }
  const s = styles[status]
  return (
    <span
      className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0"
      style={{ color: s.color, background: s.bg }}
    >
      {s.label}
    </span>
  )
}

function SummaryBar({ summary }: { summary: HealthCheckData['summary'] }) {
  const total = summary.total || 1
  const okPct  = (summary.ok   / total) * 100
  const warnPct = (summary.warn / total) * 100
  const failPct = (summary.fail / total) * 100
  return (
    <div className="space-y-2">
      <div className="flex gap-4 text-sm">
        <span style={{ color: '#4dca7e' }}>✅ {summary.ok} 정상</span>
        <span style={{ color: '#e09b3d' }}>⚠️ {summary.warn} 경고</span>
        <span style={{ color: '#e05656' }}>❌ {summary.fail} 실패</span>
        <span className="text-muted-foreground ml-auto">총 {summary.total}개</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden bg-mc-border flex">
        <div style={{ width: `${okPct}%`,   background: '#4dca7e' }} />
        <div style={{ width: `${warnPct}%`, background: '#e09b3d' }} />
        <div style={{ width: `${failPct}%`, background: '#e05656' }} />
      </div>
    </div>
  )
}

function CheckRow({ item }: { item: HealthCheckItem }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-mc-border last:border-0">
      <StatusBadge status={item.status} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-[13px] font-mono text-foreground">{item.name}</span>
          <span className="text-[12px] text-muted-foreground truncate">{item.detail}</span>
        </div>
        {item.description && (
          <div className="text-[12px] text-muted-foreground/70 mt-0.5">{item.description}</div>
        )}
      </div>
    </div>
  )
}

function CategorySection({ category, items }: { category: string; items: HealthCheckItem[] }) {
  const fail = items.filter(i => i.status === 'fail').length
  const warn = items.filter(i => i.status === 'warn').length
  const badge = fail > 0 ? `❌ ${fail}` : warn > 0 ? `⚠️ ${warn}` : '✅'
  return (
    <div className="bg-mc-card rounded-lg border border-mc-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-mc-border">
        <span className="text-[13px] font-medium">{CATEGORY_LABELS[category] ?? category}</span>
        <span className="text-[12px] font-mono">{badge} / {items.length}</span>
      </div>
      <div className="px-4">
        {items.map(item => <CheckRow key={item.name} item={item} />)}
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
  )
}

export function HealthTab() {
  const [isRunning, setIsRunning] = useState(false)

  const { data, isLoading, isValidating, mutate } = useSWR<HealthCheckData>(
    'health-status',
    fetchHealth,
    { revalidateOnFocus: false, dedupingInterval: 0 }
  )

  const isBusy = isLoading || isValidating || isRunning

  const checkedAt = data?.checked_at
    ? new Date(data.checked_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })
    : null

  async function handleRefresh() {
    if (isBusy) return
    setIsRunning(true)
    try {
      const res = await fetch('/api/health/run', { method: 'POST' })
      if (res.ok) {
        const fresh = await res.json() as HealthCheckData
        await mutate(fresh, false)  // POST 응답을 캐시에 직접 주입, 재검증 생략
      } else {
        await mutate()
      }
    } finally {
      setIsRunning(false)
    }
  }

  const grouped = CATEGORY_ORDER.reduce<Record<string, HealthCheckItem[]>>((acc, cat) => {
    const items = data?.results.filter(r => r.category === cat) ?? []
    if (items.length > 0) acc[cat] = items
    return acc
  }, {})

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold">시스템 헬스체크</h2>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            {isBusy && !isLoading
              ? '헬스체크 실행 중...'
              : checkedAt
              ? `마지막 점검: ${checkedAt}`
              : '아직 점검 결과 없음 (매일 09:00 KST 자동 실행)'}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isBusy}
          className={`flex items-center gap-1.5 text-[14px] font-mono px-2 py-0.5 rounded border transition-colors disabled:cursor-not-allowed ${
            isBusy && !isLoading
              ? 'bg-gold/10 text-gold border-gold/30'
              : 'text-muted-foreground border-mc-border hover:border-gold/30 hover:text-gold'
          }`}
        >
          {isBusy && !isLoading ? <Spinner /> : null}
          {isBusy && !isLoading ? '점검 중...' : '지금 점검'}
        </button>
      </div>

      {/* 요약 바 */}
      {data?.summary && (
        <div className={isBusy && !isLoading ? 'opacity-50 transition-opacity' : ''}>
          <SummaryBar summary={data.summary} />
        </div>
      )}

      {/* 초기 로딩 스켈레톤 */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-24 bg-mc-card rounded-lg border border-mc-border animate-pulse" />
          ))}
        </div>
      )}

      {/* 재조회 중 오버레이 */}
      {!isLoading && isBusy && data?.results.length && (
        <div className="flex items-center justify-center gap-2 py-3 text-[12px] text-muted-foreground">
          <Spinner />
          <span>데이터 조회 중...</span>
        </div>
      )}

      {/* 데이터 없음 */}
      {!isLoading && !isBusy && !data?.results.length && (
        <div className="text-center py-12 text-muted-foreground text-sm">
          헬스체크 결과가 없습니다.<br />
          매일 09:00 KST에 자동 실행됩니다.
        </div>
      )}

      {/* 카테고리별 섹션 */}
      {!isLoading && Object.entries(grouped).map(([cat, items]) => (
        <div key={cat} className={isBusy ? 'opacity-50 transition-opacity' : ''}>
          <CategorySection category={cat} items={items} />
        </div>
      ))}
    </div>
  )
}
