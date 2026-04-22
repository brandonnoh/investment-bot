import { create } from 'zustand'

export type TabId = 'overview' | 'portfolio' | 'marcus' | 'discovery' | 'wealth' | 'solar' | 'alerts' | 'system' | 'service-map'

interface MCStore {
  activeTab: TabId
  pipelineRunning: boolean
  marcusRunning: boolean
  sseStatus: 'connected' | 'disconnected'
  lastUpdated: string
  setActiveTab: (tab: TabId) => void
  setPipelineRunning: (v: boolean) => void
  setMarcusRunning: (v: boolean) => void
  setSseStatus: (v: 'connected' | 'disconnected') => void
  setLastUpdated: (v: string) => void
}

export const useMCStore = create<MCStore>((set) => ({
  activeTab: 'overview',
  pipelineRunning: false,
  marcusRunning: false,
  sseStatus: 'disconnected',
  lastUpdated: '',
  setActiveTab: (tab) => set({ activeTab: tab }),
  setPipelineRunning: (v) => set({ pipelineRunning: v }),
  setMarcusRunning: (v) => set({ marcusRunning: v }),
  setSseStatus: (v) => set({ sseStatus: v }),
  setLastUpdated: (v) => set({ lastUpdated: v }),
}))
