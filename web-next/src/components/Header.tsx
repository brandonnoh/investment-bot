'use client'

import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

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
          className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-mc-border bg-mc-bg hover:border-gold/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
        >
          {isRunningPipeline ? '\u27F3' : '\u25B6'}<span className="hidden sm:inline text-xs">{isRunningPipeline ? '\uC218\uC9D1 \uC911...' : '\uD30C\uC774\uD504\uB77C\uC778'}</span>
        </button>
        <button
          onClick={handleRunMarcus}
          disabled={isRunningMarcus}
          className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-gold/30 bg-gold/5 text-gold hover:bg-gold/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
        >
          {isRunningMarcus ? '\u27F3' : '\u2726'}<span className="hidden sm:inline text-xs">{isRunningMarcus ? '\uBD84\uC11D \uC911...' : 'AI \uBD84\uC11D'}</span>
        </button>
      </div>
    </header>
  )
}
