'use client'
import { useState } from 'react'
import { useMCStore, type TabId } from '@/store/useMCStore'

const MAIN_TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'overview',   label: '개요',    icon: '◈' },
  { id: 'portfolio',  label: '포트폴리오', icon: '◉' },
  { id: 'marcus',     label: 'AI 분석', icon: '✦' },
  { id: 'discovery',  label: '발굴',    icon: '◎' },
]

const EXTRA_TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'alerts',      label: '알림',    icon: '◬' },
  { id: 'system',      label: '시스템',  icon: '⊞' },
  { id: 'service-map', label: '서비스맵', icon: '⊟' },
]

const ALL_TABS = [...MAIN_TABS, ...EXTRA_TABS]

export function TabNav() {
  const { activeTab, setActiveTab } = useMCStore()
  const [menuOpen, setMenuOpen] = useState(false)

  const isExtraActive = EXTRA_TABS.some(t => t.id === activeTab)

  return (
    <>
      {/* 데스크탑: 상단 탭바 (전체 7개) */}
      <nav className="hidden sm:block border-b border-mc-border bg-mc-card">
        <div className="flex overflow-x-auto">
          {ALL_TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-3 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id ? 'border-gold text-gold' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* 모바일: 하단 고정 바 (4개 + 햄버거) */}
      <nav className="sm:hidden fixed bottom-0 left-0 right-0 z-50 bg-mc-card border-t border-mc-border">
        <div className="flex">
          {MAIN_TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setMenuOpen(false) }}
              className={`flex-1 flex flex-col items-center py-2 transition-colors ${
                activeTab === tab.id ? 'text-gold' : 'text-muted-foreground'
              }`}
            >
              <span className="text-xl leading-none">{tab.icon}</span>
              <span className="text-[10px] mt-0.5">{tab.label}</span>
            </button>
          ))}
          {/* 햄버거 버튼 */}
          <button
            onClick={() => setMenuOpen(o => !o)}
            className={`flex-1 flex flex-col items-center py-2 transition-colors ${
              isExtraActive ? 'text-gold' : 'text-muted-foreground'
            }`}
          >
            <span className="text-xl leading-none">{'\u2261'}</span>
            <span className="text-[10px] mt-0.5">더보기</span>
          </button>
        </div>
      </nav>

      {/* 모바일: 슬라이드업 메뉴 */}
      {menuOpen && (
        <div className="sm:hidden fixed inset-0 z-40" onClick={() => setMenuOpen(false)}>
          <div
            className="absolute bottom-[56px] left-0 right-0 bg-mc-card border-t border-mc-border"
            onClick={e => e.stopPropagation()}
          >
            {EXTRA_TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setMenuOpen(false) }}
                className={`flex items-center gap-3 w-full px-5 py-4 border-b border-mc-border last:border-0 text-sm transition-colors ${
                  activeTab === tab.id ? 'text-gold' : 'text-muted-foreground'
                }`}
              >
                <span className="text-lg">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
