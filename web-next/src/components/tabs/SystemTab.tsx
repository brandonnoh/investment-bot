'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function SystemTab() {
  const { data } = useIntelData()
  const engine = data?.engine_status

  const statusItems = [
    { label: '마지막 수집', value: engine?.last_run?.slice(0, 19) ?? '—' },
    { label: '에러 횟수', value: engine?.error_count?.toString() ?? '0' },
    { label: 'DB 용량', value: engine?.db_size_mb ? `${engine.db_size_mb.toFixed(1)} MB` : '—' },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {statusItems.map(item => (
          <Card key={item.label} className="bg-mc-card border-mc-border">
            <CardContent className="pt-3 pb-3">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="text-sm font-mono font-bold mt-0.5">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {engine?.intel_files && engine.intel_files.length > 0 && (
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">Intel 파일</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {engine.intel_files.map(file => (
                <Badge
                  key={file}
                  variant="outline"
                  className={`text-[10px] font-mono justify-start ${file.endsWith('.md') ? 'border-gold/40 text-gold' : 'border-mc-border'}`}
                >
                  {file}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
