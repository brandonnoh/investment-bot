'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function SystemTab() {
  const { data } = useIntelData()
  const engine = data?.engine_status

  const statusItems = [
    { label: '마지막 수집', value: engine?.updated_at?.slice(0, 19) ?? '—' },
    { label: '에러 횟수', value: engine?.total_errors?.toString() ?? '0' },
    { label: 'DB 용량', value: engine?.db_size_mb ? `${engine.db_size_mb.toFixed(1)} MB` : '—' },
    { label: '운영 일수', value: engine?.uptime_days != null ? `${engine.uptime_days}일` : '—' },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {statusItems.map(item => (
          <Card key={item.label} className="bg-mc-card border-mc-border">
            <CardContent className="pt-3 pb-3">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="text-sm font-mono font-bold mt-0.5">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 파이프라인 상태 뱃지 */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground font-mono">파이프라인</span>
        {engine == null ? (
          <Badge variant="outline" className="text-[10px] font-mono border-mc-border text-muted-foreground">
            정보 없음
          </Badge>
        ) : engine.pipeline_ok ? (
          <Badge variant="outline" className="text-[10px] font-mono border-mc-green text-mc-green">
            정상
          </Badge>
        ) : (
          <Badge variant="outline" className="text-[10px] font-mono border-mc-red text-mc-red">
            오류
          </Badge>
        )}
      </div>

      {/* 모듈 목록 */}
      {engine?.modules && Object.keys(engine.modules).length > 0 && (
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">모듈 현황</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
              {Object.keys(engine.modules).map(mod => (
                <Badge
                  key={mod}
                  variant="outline"
                  className="text-[10px] font-mono justify-start border-mc-border"
                >
                  {mod}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
