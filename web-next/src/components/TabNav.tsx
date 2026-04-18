'use client'

import { useMCStore, type TabId } from '@/store/useMCStore'

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'overview',     label: '개요',      icon: '◈' },
  { id: 'portfolio',    label: '포트폴리오', icon: '◉' },
  { id: 'marcus',       label: 'AI 분석',   icon: '✦' },
  { id: 'discovery',    label: '발굴',      icon: '◎' },
  { id: 'alerts',       label: '알림',      icon: '◬' },
  { id: 'system',       label: '시스템',    icon: '⊞' },
  { id: 'service-map',  label: '서비스맵',  icon: '⊟' },
]

export function TabNav() {
  const { activeTab, setActiveTab } = useMCStore()

  return (
    <>
      {/* Desktop: top tab bar */}
      <nav className="hidden sm:block border-b border-mc-border bg-mc-card">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-3 text-xs font-medium whitespace-nowrap border-b-2 transition-colors min-w-[44px] justify-center ${
                activeTab === tab.id
                  ? 'border-gold text-gold'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Mobile: bottom fixed nav */}
      <nav className="sm:hidden fixed bottom-0 left-0 right-0 z-50 bg-mc-card border-t border-mc-border">
        <div className="flex">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex flex-col items-center py-2 transition-colors ${
                activeTab === tab.id
                  ? 'text-gold'
                  : 'text-muted-foreground'
              }`}
            >
              <span className="text-xl leading-none">{tab.icon}</span>
              <span className="text-[10px] mt-0.5">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </>
  )
}
