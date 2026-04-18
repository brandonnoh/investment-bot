'use client'

import { Header } from '@/components/Header'
import { TabNav } from '@/components/TabNav'
import { OverviewTab } from '@/components/tabs/OverviewTab'
import { PortfolioTab } from '@/components/tabs/PortfolioTab'
import { MarcusTab } from '@/components/tabs/MarcusTab'
import { useMCStore } from '@/store/useMCStore'

export default function Home() {
  const { activeTab } = useMCStore()

  return (
    <div className="min-h-screen bg-mc-bg flex flex-col">
      <Header />
      <TabNav />
      <main className="flex-1 p-4 max-w-[1400px] mx-auto w-full">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'portfolio' && <PortfolioTab />}
        {activeTab === 'marcus' && <MarcusTab />}
        {activeTab !== 'overview' && activeTab !== 'portfolio' && activeTab !== 'marcus' && (
          <div className="text-muted-foreground text-sm font-mono p-8 text-center">
            {activeTab} 탭 — 구현 예정
          </div>
        )}
      </main>
    </div>
  )
}
