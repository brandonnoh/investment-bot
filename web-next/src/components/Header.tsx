'use client'

import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'
import { useIntelData } from '@/hooks/useIntelData'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

export function Header() {
  const { pipelineRunning, marcusRunning, sseStatus, lastUpdated, setPipelineRunning, setMarcusRunning } = useMCStore()
  const { pipelineRunning: pipelineActive, marcusRunning: marcusActive } = useProcessStatus()
  const { data } = useIntelData()

  const isRunningPipeline = pipelineRunning || pipelineActive
  const isRunningMarcus = marcusRunning || marcusActive

  const lastUpdatedLabel = (() => {
    if (data?.last_updated) {
      try {
        return new Date(data.last_updated).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) + ' 기준'
      } catch { /* fallback */ }
    }
    return lastUpdated || null
  })()

  async function handleRunPipeline() {
    if (isRunningPipeline) return
    setPipelineRunning(true)
    try {
      await fetch(`${BASE}/api/run-pipeline`, { method: 'POST' })
    } finally {
      setPipelineRunning(false)
    }
  }

  async function handleRunMarcus() {
    if (isRunningMarcus) return
    setMarcusRunning(true)
    try {
      await fetch(`${BASE}/api/run-marcus`, { method: 'POST' })
    } finally {
      setMarcusRunning(false)
    }
  }

  return (
    <header className="border-b border-mc-border bg-mc-card px-4 py-3 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-3">
        <span className="font-mono font-bold text-gold text-sm tracking-wider">MISSION CTRL</span>
        <div className={`w-2 h-2 rounded-full ${sseStatus === 'connected' ? 'bg-mc-green shadow-[0_0_6px_#4dca7e]' : 'bg-mc-red'}`} />
        {lastUpdatedLabel && (
          <span className="text-xs text-muted-foreground hidden sm:block">{lastUpdatedLabel}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleRunPipeline}
          disabled={isRunningPipeline}
          className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-mc-border bg-mc-bg hover:border-gold/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
        >
          {isRunningPipeline ? '⟳' : '▶'}<span className="hidden sm:inline text-xs">{isRunningPipeline ? '수집 중...' : '파이프라인'}</span>
        </button>
        <button
          onClick={handleRunMarcus}
          disabled={isRunningMarcus}
          className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-gold/30 bg-gold/5 text-gold hover:bg-gold/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
        >
          {isRunningMarcus ? '⟳' : '✦'}<span className="hidden sm:inline text-xs">{isRunningMarcus ? '분석 중...' : 'AI 분석'}</span>
        </button>
      </div>
    </header>
  )
}
