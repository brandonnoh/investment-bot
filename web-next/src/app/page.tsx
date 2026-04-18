'use client'

import { Header } from '@/components/Header'
import { TabNav } from '@/components/TabNav'
import { useMCStore } from '@/store/useMCStore'

export default function Home() {
  const { activeTab } = useMCStore()

  return (
    <div className="min-h-screen bg-mc-bg flex flex-col">
      <Header />
      <TabNav />
      <main className="flex-1 p-4 max-w-[1400px] mx-auto w-full">
        <div className="text-muted-foreground text-sm font-mono">
          탭: {activeTab} — 컴포넌트 구현 예정
        </div>
      </main>
    </div>
  )
}
