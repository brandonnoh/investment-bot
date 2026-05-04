'use client'

import { useState } from 'react'
import { useIntelData } from '@/hooks/useIntelData'

type AlertLevel = 'critical' | 'warning' | 'info'

const LEVEL_CONFIG: Record<AlertLevel, {
  dot: string
  bar: string
  bg: string
  badge: string
  label: string
  icon: string
}> = {
  critical: {
    dot: 'bg-mc-red shadow-[0_0_6px_#e05656]',
    bar: 'bg-mc-red',
    bg: 'bg-mc-red/5',
    badge: 'text-mc-red bg-mc-red/10 border-mc-red/30',
    label: 'CRITICAL',
    icon: '●',
  },
  warning: {
    dot: 'bg-amber',
    bar: 'bg-amber',
    bg: 'bg-amber/5',
    badge: 'text-amber bg-amber/10 border-amber/30',
    label: 'WARNING',
    icon: '▲',
  },
  info: {
    dot: 'bg-muted-foreground/40',
    bar: 'bg-mc-border',
    bg: '',
    badge: 'text-muted-foreground bg-mc-border/20 border-mc-border',
    label: 'INFO',
    icon: '◆',
  },
}

const FILTERS: { id: AlertLevel | 'all'; label: string }[] = [
  { id: 'all', label: '전체' },
  { id: 'critical', label: 'CRITICAL' },
  { id: 'warning', label: 'WARNING' },
  { id: 'info', label: 'INFO' },
]

function fmtTime(ts: string | undefined): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleString('ko-KR', {
      month: 'numeric', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return ts.slice(0, 16) }
}

function levelKey(raw: string | undefined): AlertLevel {
  const l = (raw ?? '').toLowerCase()
  if (l === 'critical' || l === 'red') return 'critical'
  if (l === 'warning' || l === 'yellow') return 'warning'
  return 'info'
}

export function AlertsTab() {
  const { data } = useIntelData()
  const alerts = data?.alerts?.alerts ?? []
  const triggeredAt = data?.alerts?.triggered_at

  const [filter, setFilter] = useState<AlertLevel | 'all'>('all')

  const counts = {
    critical: alerts.filter(a => levelKey(a.level) === 'critical').length,
    warning:  alerts.filter(a => levelKey(a.level) === 'warning').length,
    info:     alerts.filter(a => levelKey(a.level) === 'info').length,
  }

  const visible = filter === 'all' ? alerts : alerts.filter(a => levelKey(a.level) === filter)

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-2">
        <span className="text-2xl text-mc-border">◆</span>
        <span className="text-sm text-muted-foreground">현재 활성 알림이 없습니다</span>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 요약 헤더 */}
      <div className="flex items-center justify-between rounded-md border border-mc-border bg-mc-card px-4 py-2.5">
        <div className="flex items-center gap-4">
          {counts.critical > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-mc-red shadow-[0_0_6px_#e05656]" />
              <span className="text-xs font-mono text-mc-red">{counts.critical} critical</span>
            </div>
          )}
          {counts.warning > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber" />
              <span className="text-xs font-mono text-amber">{counts.warning} warning</span>
            </div>
          )}
          {counts.info > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-muted-foreground/40" />
              <span className="text-xs font-mono text-muted-foreground">{counts.info} info</span>
            </div>
          )}
        </div>
        {triggeredAt && (
          <span className="text-[14px] text-muted-foreground">{fmtTime(triggeredAt)}</span>
        )}
      </div>

      {/* 필터 칩 */}
      <div className="flex gap-1.5">
        {FILTERS.map(f => {
          const active = filter === f.id
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className="text-[14px] font-medium px-3 py-1 rounded-full border transition-colors"
              style={{
                borderColor: active ? '#4dca7e' : '#2a2420',
                background: active ? 'rgba(77,202,126,0.15)' : 'transparent',
                color: active ? '#4dca7e' : '#9a8e84',
              }}
            >
              {f.label}
              {f.id !== 'all' && counts[f.id] > 0 && (
                <span className="ml-1 opacity-70">{counts[f.id]}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* 타임라인 */}
      <div className="relative">
        {/* 수직 선 */}
        <div className="absolute left-[7px] top-2 bottom-2 w-px bg-mc-border" />

        <div className="space-y-0">
          {visible.map((alert, i) => {
            const lv = levelKey(alert.level)
            const cfg = LEVEL_CONFIG[lv]
            return (
              <div key={i} className="relative flex gap-3 pb-3 last:pb-0">
                {/* 타임라인 점 */}
                <div className="relative z-10 mt-3 shrink-0">
                  <span className={`block w-3.5 h-3.5 rounded-full border-2 border-mc-card ${cfg.dot}`} />
                </div>

                {/* 카드 */}
                <div className={`flex-1 rounded-md border border-mc-border ${cfg.bg} px-3 py-2.5`}
                  style={lv === 'critical' ? { borderLeftWidth: '3px', borderLeftColor: '#e05656' }
                       : lv === 'warning'  ? { borderLeftWidth: '3px', borderLeftColor: '#e09b3d' }
                       : undefined}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[14px] font-mono font-bold px-1.5 py-0.5 rounded border ${cfg.badge}`}>
                      {cfg.icon} {cfg.label}
                    </span>
                    {alert.ticker && (
                      <span className="text-xs font-mono text-muted-foreground">{alert.ticker}</span>
                    )}
                    <span className="text-[14px] text-muted-foreground ml-auto font-mono">
                      {fmtTime(alert.triggered_at ?? triggeredAt)}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed">{alert.message}</p>
                  {(alert.value !== undefined || alert.threshold !== undefined) && (
                    <div className="text-[14px] text-muted-foreground mt-1.5 font-mono flex gap-3">
                      {alert.value !== undefined && (
                        <span>값 <span className="text-foreground">{alert.value}</span></span>
                      )}
                      {alert.threshold !== undefined && (
                        <span>임계 <span className="text-foreground">{alert.threshold}</span></span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
