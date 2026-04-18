# task-003: 레이아웃 + Header + 탭 네비게이션 + 글로벌 상태

## 배경
현재 헤더(web/index.html 줄 18-53)와 탭(줄 56-102)을 React 컴포넌트로 분리. Zustand 스토어로 탭 상태 관리.

## 현재 코드 구조
- `web/index.html` 줄 18-53: Header — 브랜드 + 파이프라인 버튼 + AI분석 버튼 + 시간 + live dot
- `web/index.html` 줄 56-102: nav.tabs — 7개 탭 버튼 (svg + .tab-label span)
- `web/static/app.js` 줄 10-70: Alpine.js 스토어 — tab, pipelineRunning, marcusRunning, lastUpdated, sseStatus

## 구현 방향

### web-next/src/store/useMCStore.ts (Zustand)
```typescript
import { create } from 'zustand'

type Tab = 'overview' | 'portfolio' | 'marcus' | 'discovery' | 'alerts' | 'system' | 'map'

interface MCStore {
  tab: Tab
  setTab: (tab: Tab) => void
  lastUpdated: string | null
  setLastUpdated: (t: string) => void
  sseStatus: 'connected' | 'disconnected'
  setSseStatus: (s: 'connected' | 'disconnected') => void
}

export const useMCStore = create<MCStore>((set) => ({
  tab: 'overview',
  setTab: (tab) => set({ tab }),
  lastUpdated: null,
  setLastUpdated: (lastUpdated) => set({ lastUpdated }),
  sseStatus: 'disconnected',
  setSseStatus: (sseStatus) => set({ sseStatus }),
}))
```

### web-next/src/app/layout.tsx
```typescript
import type { Metadata } from 'next'
import { Space_Grotesk, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-sans' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = { title: 'Mission Control' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className={`${spaceGrotesk.variable} ${jetbrainsMono.variable} font-sans bg-mc-bg text-foreground min-h-screen antialiased`}>
        {children}
      </body>
    </html>
  )
}
```

### web-next/src/app/page.tsx
```typescript
'use client'
import { Header } from '@/components/Header'
import { TabNav } from '@/components/TabNav'
import { TabContent } from '@/components/TabContent'
import { SSEProvider } from '@/components/SSEProvider'

export default function Page() {
  return (
    <SSEProvider>
      <Header />
      <TabNav />
      <main className="max-w-[1440px] mx-auto p-6 md:p-4 sm:p-3">
        <TabContent />
      </main>
    </SSEProvider>
  )
}
```

### web-next/src/components/Header.tsx
현재 web/index.html 줄 18-53 대응:
```typescript
'use client'
import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'
import { runPipeline, runMarcus } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function Header() {
  const { lastUpdated, sseStatus } = useMCStore()
  const { pipelineRunning, marcusRunning, mutate } = useProcessStatus()

  return (
    <header className="sticky top-0 z-50 flex items-center gap-4 px-6 h-[52px] bg-mc-card border-b border-mc-border">
      {/* 브랜드 */}
      <div className="flex items-center gap-2 text-[13px] font-semibold tracking-widest uppercase text-gold whitespace-nowrap">
        <div className="w-5 h-5 border border-gold rounded-sm flex items-center justify-center">
          <ActivityIcon size={11} />
        </div>
        <span className="hidden sm:inline">MISSION CTRL</span>
      </div>

      {/* 액션 영역 */}
      <div className="ml-auto flex items-center gap-2.5">
        <Button
          size="sm"
          variant="outline"
          disabled={pipelineRunning}
          onClick={() => { runPipeline(); mutate() }}
          className="border-gold/40 text-gold hover:bg-gold/8 h-9 sm:h-8 text-xs"
        >
          {pipelineRunning ? <><Spinner /> 실행 중</> : <><PlayIcon size={11} /> 파이프라인</>}
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={marcusRunning}
          onClick={() => { runMarcus(); mutate() }}
          className="border-mc-border text-muted hover:text-foreground h-9 sm:h-8 text-xs"
        >
          {marcusRunning ? <><Spinner /> 분석 중</> : <><BrainIcon size={11} /> AI 분석</>}
        </Button>

        <span className="hidden sm:block font-mono text-[10px] text-muted-foreground">
          {lastUpdated ?? '--:--'}
        </span>

        <div className={`w-2 h-2 rounded-full ${
          sseStatus === 'connected'
            ? 'bg-mc-green shadow-[0_0_5px_#4dca7e]'
            : 'bg-mc-red shadow-[0_0_5px_#e05656]'
        }`} />
      </div>
    </header>
  )
}
```

### web-next/src/components/TabNav.tsx
7개 탭, 모바일에서 `.tab-label` 숨김:
```typescript
const TABS = [
  { id: 'overview',   label: '개요',     Icon: BarChart3Icon },
  { id: 'portfolio',  label: '포트폴리오', Icon: LayersIcon },
  { id: 'marcus',     label: 'AI 분석',  Icon: ActivityIcon },
  { id: 'discovery',  label: '발굴',     Icon: SearchIcon },
  { id: 'alerts',     label: '알림',     Icon: BellIcon },
  { id: 'system',     label: '시스템',   Icon: CpuIcon },
  { id: 'map',        label: '서비스 맵', Icon: MapIcon },
] as const

export function TabNav() {
  const { tab, setTab } = useMCStore()
  return (
    <nav className="flex bg-mc-card border-b border-mc-border px-6 overflow-x-auto scrollbar-hide">
      {TABS.map(({ id, label, Icon }) => (
        <button
          key={id}
          onClick={() => setTab(id)}
          className={`inline-flex items-center gap-1.5 px-4 h-11 text-xs font-medium tracking-wide whitespace-nowrap border-b-2 transition-colors
            ${tab === id
              ? 'text-gold border-gold'
              : 'text-muted-foreground border-transparent hover:text-muted'
            }`}
        >
          <Icon size={13} />
          <span className="tab-label hidden sm:inline">{label}</span>
          {/* 알림 뱃지는 AlertsTab에서 별도 처리 */}
        </button>
      ))}
    </nav>
  )
}
```

### web-next/src/components/TabContent.tsx
```typescript
'use client'
import { useMCStore } from '@/store/useMCStore'
import { OverviewTab } from './tabs/OverviewTab'
import { PortfolioTab } from './tabs/PortfolioTab'
// ... 나머지 탭

export function TabContent() {
  const { tab } = useMCStore()
  return (
    <>
      {tab === 'overview'   && <OverviewTab />}
      {tab === 'portfolio'  && <PortfolioTab />}
      {tab === 'marcus'     && <MarcusTab />}
      {tab === 'discovery'  && <DiscoveryTab />}
      {tab === 'alerts'     && <AlertsTab />}
      {tab === 'system'     && <SystemTab />}
      {tab === 'map'        && <ServiceMapTab />}
    </>
  )
}
```

## 아이콘 라이브러리
`lucide-react` 사용:
```bash
npm install lucide-react
```

## 검증
```bash
cd web-next && npm run build
```
