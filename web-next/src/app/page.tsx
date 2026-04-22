'use client'

import { Header } from '@/components/Header'
import { TabNav } from '@/components/TabNav'
import { OverviewTab } from '@/components/tabs/OverviewTab'
import { PortfolioTab } from '@/components/tabs/PortfolioTab'
import { MarcusTab } from '@/components/tabs/MarcusTab'
import { DiscoveryTab } from '@/components/tabs/DiscoveryTab'
import { AlertsTab } from '@/components/tabs/AlertsTab'
import { SystemTab } from '@/components/tabs/SystemTab'
import { ServiceMapTab } from '@/components/tabs/ServiceMapTab'
import { WealthTab } from '@/components/tabs/WealthTab'
import { SolarTab } from '@/components/tabs/SolarTab'
import { SSEProvider } from '@/components/SSEProvider'
import { useMCStore } from '@/store/useMCStore'
import { useIntelData } from '@/hooks/useIntelData'
import { useRefresh } from '@/hooks/useRefresh'
import { usePullToRefresh } from '@/hooks/usePullToRefresh'

export default function Home() {
  const { activeTab } = useMCStore()
  const { mutate } = useIntelData()
  const { refresh, isRefreshing } = useRefresh(mutate)

  // 모바일: 최상단에서 80px 이상 아래로 당기면 새로고침
  usePullToRefresh(refresh)

  return (
    <SSEProvider>
      <div className="min-h-screen bg-mc-bg flex flex-col">
        {isRefreshing && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-mc-bg/80 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-gold border-t-transparent rounded-full animate-spin" />
              <p className="text-xs font-mono text-gold tracking-widest uppercase animate-pulse">
                가격 수집 중…
              </p>
            </div>
          </div>
        )}
        <Header />
        <TabNav />
        <main className="flex-1 p-4 pb-20 sm:pb-4 max-w-[1400px] mx-auto w-full">
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'portfolio' && <PortfolioTab />}
          {activeTab === 'marcus' && <MarcusTab />}
          {activeTab === 'discovery' && <DiscoveryTab />}
          {activeTab === 'wealth' && <WealthTab />}
          {activeTab === 'solar' && <SolarTab />}
          {activeTab === 'alerts' && <AlertsTab />}
          {activeTab === 'system' && <SystemTab />}
          {activeTab === 'service-map' && <ServiceMapTab />}
        </main>
      </div>
    </SSEProvider>
  )
}
