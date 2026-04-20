'use client'
import { useWealthData } from '@/hooks/useWealthData'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtKrw } from '@/lib/format'
import { SyncBadge } from '@/components/SyncBadge'

const TYPE_COLOR: Record<string, string> = {
  '부동산': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  '연금': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  '적금': 'bg-green-500/20 text-green-300 border-green-500/30',
  '청약': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
}

interface ExtraAsset {
  name: string
  type: string
  current_value_krw: number
  monthly_deposit_krw: number
  is_fixed: boolean
  maturity_date: string | null
  note: string | null
}

export function WealthTab() {
  const { data, isLoading } = useWealthData()

  if (isLoading) return <div className="text-muted-foreground text-sm p-4">로딩 중...</div>
  if (!data) return null

  const investPct = data.total_wealth_krw > 0 ? (data.investment_krw / data.total_wealth_krw) * 100 : 0
  const extraPct = 100 - investPct

  return (
    <div className="space-y-4">
      {/* Hero */}
      <Card className="bg-mc-card border-mc-border">
        <CardContent className="pt-5 pb-5 px-5">
          <div className="text-xs text-muted-foreground mb-1">
            전체 자산<SyncBadge timestamp={data.last_updated} />
          </div>
          <div className="text-3xl font-mono font-bold">
            {fmtKrw(data.total_wealth_krw)}<span className="text-lg font-normal text-muted-foreground ml-1">원</span>
          </div>
          <div className="flex gap-4 mt-3 text-xs font-mono text-muted-foreground">
            <span>투자 <span className="text-foreground font-semibold">{fmtKrw(data.investment_krw)}원</span></span>
            <span>비금융 <span className="text-foreground font-semibold">{fmtKrw(data.extra_assets_krw)}원</span></span>
          </div>
          {/* 비율 바 */}
          <div className="flex h-2 rounded-full overflow-hidden mt-3 gap-px">
            <div style={{ width: `${investPct}%` }} className="bg-gold" />
            <div style={{ width: `${extraPct}%` }} className="bg-mc-border" />
          </div>
          <div className="flex gap-3 mt-1.5 text-[10px] text-muted-foreground">
            <span><span className="inline-block w-2 h-2 rounded-sm bg-gold mr-1" />투자 {investPct.toFixed(0)}%</span>
            <span><span className="inline-block w-2 h-2 rounded-sm bg-mc-border mr-1" />비금융 {extraPct.toFixed(0)}%</span>
          </div>
        </CardContent>
      </Card>

      {/* 비금융 자산 리스트 */}
      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-xs font-mono">비금융 자산</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="space-y-0">
            {data.extra_assets.map((a: ExtraAsset) => (
              <div key={a.name} className="flex items-center justify-between py-3 border-b border-mc-border last:border-0">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${TYPE_COLOR[a.type] ?? 'bg-muted text-muted-foreground border-border'}`}>
                    {a.type}
                  </span>
                  <div>
                    <div className="text-sm font-medium">{a.name}</div>
                    {a.monthly_deposit_krw > 0 && (
                      <div className="text-[10px] text-muted-foreground">월 +{fmtKrw(a.monthly_deposit_krw)}원</div>
                    )}
                  </div>
                </div>
                <div className="text-sm font-mono font-semibold">{fmtKrw(a.current_value_krw)}원</div>
              </div>
            ))}
          </div>
          {data.monthly_recurring_krw > 0 && (
            <div className="mt-3 pt-3 border-t border-mc-border text-xs text-muted-foreground font-mono">
              매월 <span className="text-gold font-semibold">{fmtKrw(data.monthly_recurring_krw)}원</span> 자동 적립 중
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
