# task-008: SSE 실시간 연결 + 파이프라인/Marcus 실행 연동

## 배경
현재 app.js의 SSE 연결(줄 72-88)과 폴링 로직을 React 훅으로 이전.

## 현재 코드 구조 (app.js)
- 줄 72-88: `startSSE()` — `/api/events` EventSource 연결, 메시지 수신 시 fetchData() 호출
- 줄 306-317: `runPipeline()` — POST + 상태 폴링
- 줄 341-415: `runMarcus()` — POST + 로그 폴링

## 구현 방향

### web-next/src/hooks/useSSE.ts
```typescript
'use client'
import { useEffect } from 'react'
import { useSWRConfig } from 'swr'
import { useMCStore } from '@/store/useMCStore'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8421'

export function useSSE() {
  const { mutate } = useSWRConfig()
  const { setSseStatus, setLastUpdated } = useMCStore()

  useEffect(() => {
    const es = new EventSource(`${BASE}/api/events`)

    es.onopen = () => setSseStatus('connected')
    es.onerror = () => setSseStatus('disconnected')

    es.onmessage = () => {
      mutate('intel-data')       // SWR 캐시 무효화 → 자동 재조회
      mutate('process-status')
      setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }))
    }

    return () => es.close()
  }, [mutate, setSseStatus, setLastUpdated])
}
```

### web-next/src/components/SSEProvider.tsx
```typescript
'use client'
import { useSSE } from '@/hooks/useSSE'

export function SSEProvider({ children }: { children: React.ReactNode }) {
  useSSE()
  return <>{children}</>
}
```

### Marcus 라이브 로그 훅 (web-next/src/hooks/useMarcusLog.ts)
```typescript
// marcusRunning이 true일 때 /api/logs?name=marcus&lines=100 을 3초마다 폴링
import useSWR from 'swr'
import { fetchLogs } from '@/lib/api'

export function useMarcusLog(enabled: boolean) {
  const { data } = useSWR(
    enabled ? 'marcus-log' : null,
    () => fetchLogs('marcus', 100),
    { refreshInterval: 3_000 }
  )
  return data?.lines ?? []
}
```

### MarcusTab에 라이브 로그 통합
분석 실행 중일 때 로그 뷰어 표시:
```tsx
// useMarcusLog(marcusRunning) 호출
// 로그 라인 색상:
//   "✅" 포함 → text-mc-green
//   "❌" 포함 → text-mc-red
//   "⚠" 포함 → text-amber
//   else → text-muted-foreground
```

## 검증
```bash
cd web-next && npm run build
```
