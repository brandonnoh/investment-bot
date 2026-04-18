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
import { SSEProvider } from '@/components/SSEProvider'
import { useMCStore } from '@/store/useMCStore'

export default function Home() {
  const { activeTab } = useMCStore()

  return (
    <SSEProvider>
      <div className="min-h-screen bg-mc-bg flex flex-col">
        <Header />
        <TabNav />
        <main className="flex-1 p-4 max-w-[1400px] mx-auto w-full">
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'portfolio' && <PortfolioTab />}
          {activeTab === 'marcus' && <MarcusTab />}
          {activeTab === 'discovery' && <DiscoveryTab />}
          {activeTab === 'alerts' && <AlertsTab />}
          {activeTab === 'system' && <SystemTab />}
          {activeTab === 'service-map' && <ServiceMapTab />}
        </main>
      </div>
    </SSEProvider>
  )
}
