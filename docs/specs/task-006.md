# task-006: AI 분석 탭 — Marcus 결과 + 이력 사이드패널

## 배경
app.js 줄 319-415의 AI 분석 로직(fetchAnalysisHistory, runMarcus 폴링, 라이브 로그)을 React 훅으로 이전.

## 현재 코드 구조 (app.js)
- 줄 319-340: `fetchAnalysisHistory()` — /api/analysis-history GET
- 줄 341-415: `runMarcus()` — POST → SSE 폴링 → 로그 스트리밍
- HTML: `.ai-layout` (1fr 280px) — 메인(마크다운) + 사이드(이력 목록)

## 구현 방향

### web-next/src/components/tabs/MarcusTab.tsx
```typescript
'use client'
import { useState } from 'react'
import { useAnalysisHistory } from '@/hooks/useAnalysisHistory'
import { useIntelData } from '@/hooks/useIntelData'
import ReactMarkdown from 'react-markdown'
import { Card } from '@/components/ui/card'

export function MarcusTab() {
  const { data: intel } = useIntelData()
  const { history } = useAnalysisHistory()
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [detail, setDetail] = useState<string | null>(null)

  const currentMd = detail ?? intel?.marcus_analysis ?? ''

  async function loadDetail(date: string) {
    setSelectedDate(date)
    const res = await fetch(`${BASE}/api/analysis-history?date=${date}`)
    const d = await res.json()
    setDetail(d?.analysis ?? '')
  }

  return (
    <div className="grid grid-cols-[1fr_280px] gap-4 sm:grid-cols-1 sm:flex sm:flex-col-reverse">
      {/* 메인: 마크다운 결과 */}
      <Card className="bg-mc-card border-mc-border p-4 min-w-0">
        {currentMd
          ? <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{currentMd}</ReactMarkdown>
            </div>
          : <p className="text-muted-foreground text-sm">분석 결과 없음 — AI 분석 버튼을 눌러 실행하세요.</p>
        }
      </Card>

      {/* 사이드: 이력 목록 */}
      <div className="space-y-2">
        {history.map(h => (
          <button
            key={h.date}
            onClick={() => loadDetail(h.date)}
            className={`w-full text-left p-3 rounded border transition-colors ${
              selectedDate === h.date
                ? 'border-gold bg-gold/8'
                : 'border-mc-border bg-mc-card hover:border-mc-border/70'
            }`}
          >
            <div className="font-mono text-xs font-semibold">{h.date}</div>
            <div className="flex gap-2 items-center mt-1">
              {h.confidence_level && (
                <span className="text-[10px] text-gold">{'★'.repeat(h.confidence_level)}</span>
              )}
              {h.stance && (
                <span className="text-[10px] text-muted-foreground">{h.stance}</span>
              )}
            </div>
            {h.today_call && (
              <div className="text-[11px] text-muted-foreground mt-1 line-clamp-2">{h.today_call}</div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
```

### web-next/src/hooks/useAnalysisHistory.ts
```typescript
import useSWR from 'swr'
import { fetchAnalysisHistory } from '@/lib/api'

export function useAnalysisHistory() {
  const { data } = useSWR('analysis-history', fetchAnalysisHistory)
  return { history: data ?? [] }
}
```

### 타입 추가 (web-next/src/types/api.ts에 추가)
```typescript
export interface AnalysisHistory {
  date: string
  confidence_level?: number
  stance?: string
  today_call?: string
}

export interface AnalysisDetail {
  date: string
  analysis: string
}
```

### react-markdown 설치
```bash
npm install react-markdown
```

## 검증
```bash
cd web-next && npm run build
```
