# task-004: 개요 탭 — StatsStrip + HoldingsTable + 사이드바

## 배경
현재 web/index.html 줄 107-273의 개요 탭을 React 컴포넌트로 구현.

## 현재 코드 구조
- 줄 111-141: StatsStrip — 포트폴리오 손익 / 평균 일변동 / 시장 국면 / 활성 알림
- 줄 143-183: HoldingsTable — 종목명/현재가/등락/평균단가/평가손익/통화
- 줄 185-257: 사이드바 — 시장국면 카드 + Fear&Greed + 매크로
- 줄 260-273: 활성 알림 배너

## 구현 방향

### web-next/src/components/tabs/OverviewTab.tsx
```typescript
'use client'
import { useIntelData } from '@/hooks/useIntelData'
import { StatsStrip } from '@/components/overview/StatsStrip'
import { HoldingsTable } from '@/components/overview/HoldingsTable'
import { MarketSidebar } from '@/components/overview/MarketSidebar'
import { AlertBanner } from '@/components/overview/AlertBanner'

export function OverviewTab() {
  const { data, isLoading } = useIntelData()

  if (isLoading) return <div className="animate-pulse p-4 text-muted-foreground text-sm">로딩 중...</div>

  return (
    <div className="space-y-4">
      <StatsStrip data={data} />
      <AlertBanner alerts={data?.alerts?.alerts ?? []} />
      <div className="grid grid-cols-[1fr_280px] gap-4 lg:grid-cols-1">
        <HoldingsTable prices={data?.prices ?? []} />
        <MarketSidebar data={data} />
      </div>
    </div>
  )
}
```

### StatsStrip 컴포넌트
shadcn Card 4개 가로 배열, 모바일 2×2:
```typescript
// 4개 stat: 포트폴리오 손익 / 평균 일변동 / 시장 국면 / 활성 알림
// 색상 유틸:
function pctColor(v?: number | null) {
  if (v == null) return 'text-muted-foreground'
  return v > 0 ? 'text-mc-green' : v < 0 ? 'text-mc-red' : 'text-muted-foreground'
}
```

```tsx
<div className="grid grid-cols-4 sm:grid-cols-2 border border-mc-border rounded-lg overflow-hidden bg-mc-card">
  {stats.map((s, i) => (
    <div key={i} className="p-4 border-r border-mc-border last:border-r-0 sm:[&:nth-child(2)]:border-r-0 sm:border-b sm:[&:nth-last-child(-n+2)]:border-b-0">
      <div className="text-xs text-muted-foreground mb-1">{s.label}</div>
      <div className={`text-lg font-mono font-semibold ${s.color}`}>{s.value}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{s.sub}</div>
    </div>
  ))}
</div>
```

### HoldingsTable 컴포넌트
shadcn Table 사용:
```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

// 컬럼: 종목 / 현재가 / 등락 / 평균단가 / 평가손익 / 통화
// 현재가: currency === 'USD' ? `$${price.toFixed(2)}` : price.toLocaleString('ko-KR')
// 등락: fmtPct 유틸 (±X.XX%)
```

### MarketSidebar 컴포넌트
```tsx
// 시장국면 Card
<Card className="bg-mc-card border-mc-border">
  <CardHeader className="py-3 px-4">
    <CardTitle className="text-xs font-semibold">시장 국면</CardTitle>
  </CardHeader>
  <CardContent className="px-4 pb-4 space-y-2">
    <KVRow label="국면" value={regime?.regime} color={regimeColor(regime?.regime)} />
    <KVRow label="신뢰도" value={`${((regime?.confidence ?? 0) * 100).toFixed(0)}%`} />
    <KVRow label="VIX" value={regime?.vix?.toFixed(2)} color={vixColor(regime?.vix)} />
    <KVRow label="현금 비중" value={`${((regime?.strategy?.cash_ratio ?? 0) * 100).toFixed(0)}%`} />
  </CardContent>
</Card>

// Fear & Greed Card
<Card>
  <CardContent>
    <div className="text-3xl font-mono font-bold text-center">{score}</div>
    <div className="text-sm text-center text-muted-foreground">{rating}</div>
    <Progress value={score} className="mt-2" />
    <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
      <span>공포</span><span>탐욕</span>
    </div>
  </CardContent>
</Card>

// 매크로 Card (상위 4개)
```

### 유틸 함수 (web-next/src/lib/format.ts)
```typescript
export function fmtPct(v?: number | null): string {
  if (v == null) return '-'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

export function fmtKrw(v?: number | null): string {
  if (v == null) return '-'
  return v.toLocaleString('ko-KR') + '원'
}

export function fmtNum(v?: number | null, digits = 2): string {
  if (v == null) return '-'
  return v.toFixed(digits)
}

export function pctColor(v?: number | null): string {
  if (v == null) return 'text-muted-foreground'
  return v > 0 ? 'text-mc-green' : v < 0 ? 'text-mc-red' : 'text-muted-foreground'
}

export function regimeColor(regime?: string): string {
  const map: Record<string, string> = {
    RISK_ON: 'text-mc-green',
    RISK_OFF: 'text-mc-red',
    NEUTRAL: 'text-gold',
  }
  return map[regime ?? ''] ?? 'text-muted-foreground'
}
```

## 검증
```bash
cd web-next && npm run build
```
