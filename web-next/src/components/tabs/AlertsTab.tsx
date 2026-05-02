'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { Badge } from '@/components/ui/badge'

const LEVEL_STYLES: Record<string, string> = {
  critical: 'border-l-4 border-l-mc-red bg-mc-red/5',
  warning:  'border-l-4 border-l-amber bg-amber/5',
  info:     'border-l-4 border-l-mc-border',
}

const LEVEL_BADGE: Record<string, string> = {
  critical: 'bg-mc-red/10 text-mc-red border-mc-red/30',
  warning:  'bg-amber/10 text-amber border-amber/30',
  info:     'bg-mc-border/20 text-muted-foreground border-mc-border',
}

export function AlertsTab() {
  const { data } = useIntelData()
  const alerts = data?.alerts?.alerts ?? []

  if (alerts.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
        현재 활성 알림이 없습니다
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
      {alerts.map((alert, i) => (
        <div key={i} className={`p-3 rounded border ${LEVEL_STYLES[alert.level] ?? LEVEL_STYLES.info}`}>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className={`text-[14px] ${LEVEL_BADGE[alert.level] ?? ''}`}>
              {alert.level}
            </Badge>
            {alert.ticker && (
              <span className="text-xs font-mono text-muted-foreground">{alert.ticker}</span>
            )}
            {alert.triggered_at && (
              <span className="text-[14px] text-muted-foreground ml-auto">{alert.triggered_at.slice(0, 10)}</span>
            )}
          </div>
          <p className="text-xs">{alert.message}</p>
          {(alert.value !== undefined || alert.threshold !== undefined) && (
            <div className="text-[14px] text-muted-foreground mt-1 font-mono">
              {alert.value !== undefined && `값: ${alert.value}`}
              {alert.threshold !== undefined && ` / 임계값: ${alert.threshold}`}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
