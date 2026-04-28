import { create } from 'zustand'

export type TabId = 'overview' | 'portfolio' | 'marcus' | 'discovery' | 'wealth' | 'solar' | 'alerts' | 'system' | 'service-map' | 'advisor' | 'saved-strategies'

const VALID_TABS: TabId[] = [
  'overview', 'portfolio', 'marcus', 'discovery', 'wealth',
  'solar', 'alerts', 'system', 'service-map', 'advisor', 'saved-strategies',
]

interface MCStore {
  activeTab: TabId
  pipelineRunning: boolean
  marcusRunning: boolean
  sseStatus: 'connected' | 'disconnected'
  lastUpdated: string
  marcusPickedTicker: string | null
  setActiveTab: (tab: TabId) => void
  setPipelineRunning: (v: boolean) => void
  setMarcusRunning: (v: boolean) => void
  setSseStatus: (v: 'connected' | 'disconnected') => void
  setLastUpdated: (v: string) => void
  setMarcusPickedTicker: (ticker: string | null) => void
  jumpToDiscovery: (ticker: string) => void
}

function getInitialTab(): TabId {
  if (typeof window === 'undefined') return 'overview'
  try {
    // URL ?tab= 우선, 없으면 localStorage 폴백
    const urlTab = new URLSearchParams(window.location.search).get('tab') as TabId | null
    if (urlTab && VALID_TABS.includes(urlTab)) return urlTab
    return (localStorage.getItem('mc-active-tab') as TabId) ?? 'overview'
  } catch {
    return 'overview'
  }
}

function syncUrl(tab: TabId) {
  if (typeof window === 'undefined') return
  const url = new URL(window.location.href)
  url.searchParams.set('tab', tab)
  window.history.replaceState(null, '', url.toString())
}

export const useMCStore = create<MCStore>((set) => ({
  activeTab: getInitialTab(),
  pipelineRunning: false,
  marcusRunning: false,
  sseStatus: 'disconnected',
  lastUpdated: '',
  marcusPickedTicker: null,
  setActiveTab: (tab) => {
    try { localStorage.setItem('mc-active-tab', tab) } catch {}
    syncUrl(tab)
    set({ activeTab: tab })
  },
  setPipelineRunning: (v) => set({ pipelineRunning: v }),
  setMarcusRunning: (v) => set({ marcusRunning: v }),
  setSseStatus: (v) => set({ sseStatus: v }),
  setLastUpdated: (v) => set({ lastUpdated: v }),
  setMarcusPickedTicker: (ticker) => set({ marcusPickedTicker: ticker }),
  jumpToDiscovery: (ticker) => {
    syncUrl('discovery')
    set({ activeTab: 'discovery', marcusPickedTicker: ticker })
  },
}))
