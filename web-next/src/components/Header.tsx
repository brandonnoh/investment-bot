'use client'

import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8421'

export function Header() {
  const { pipelineRunning, marcusRunning, sseStatus, lastUpdated, setPipelineRunning, setMarcusRunning } = useMCStore()
  const { pipelineRunning: pipelineActive, marcusRunning: marcusActive } = useProcessStatus()

  const isRunningPipeline = pipelineRunning || pipelineActive
  const isRunningMarcus = marcusRunning || marcusActive

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
        {lastUpdated && <span className="text-xs text-muted-foreground hidden sm:block">{lastUpdated}</span>}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleRunPipeline}
          disabled={isRunningPipeline}
          className="text-xs px-3 py-1.5 rounded border border-mc-border bg-mc-bg hover:border-gold/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunningPipeline ? '\u27F3 \uC218\uC9D1 \uC911...' : '\u25B6 \uD30C\uC774\uD504\uB77C\uC778'}
        </button>
        <button
          onClick={handleRunMarcus}
          disabled={isRunningMarcus}
          className="text-xs px-3 py-1.5 rounded border border-gold/30 bg-gold/5 text-gold hover:bg-gold/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunningMarcus ? '\u27F3 \uBD84\uC11D \uC911...' : '\u2726 AI \uBD84\uC11D'}
        </button>
      </div>
    </header>
  )
}
