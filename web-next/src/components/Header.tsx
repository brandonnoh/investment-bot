'use client'

import { useTheme } from 'next-themes'
import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'
import { useIntelData } from '@/hooks/useIntelData'
import { useRefresh } from '@/hooks/useRefresh'
import { useEffect, useState } from 'react'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

export function Header() {
  const { pipelineRunning, marcusRunning, sseStatus, lastUpdated, setPipelineRunning, setMarcusRunning } = useMCStore()
  const { pipelineRunning: pipelineActive, marcusRunning: marcusActive } = useProcessStatus()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // SWR 캐시가 공유되므로 추가 네트워크 요청 없이 mutate만 사용
  const { data, mutate } = useIntelData()
  const { refresh, isRefreshing } = useRefresh(mutate)

  useEffect(() => {
    setMounted(true)
  }, [])

  const isRunningPipeline = pipelineRunning || pipelineActive
  const isRunningMarcus = marcusRunning || marcusActive

  // 마지막 업데이트 시각: API 데이터 우선, 없으면 SSE lastUpdated 사용
  const lastUpdatedLabel = (() => {
    if (data?.last_updated) {
      try {
        return new Date(data.last_updated).toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
        }) + ' 기준'
      } catch {
        // 파싱 실패 시 fallback
      }
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
        {/* 수동 새로고침 버튼 */}
        <button
          onClick={refresh}
          disabled={isRefreshing}
          className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-mc-border bg-mc-bg hover:border-gold/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          title="데이터 새로고침"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
            <path d="M21 3v5h-5" />
          </svg>
        </button>

        {mounted && (
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="text-sm px-2 py-1.5 min-h-[36px] min-w-[36px] rounded border border-mc-border bg-mc-bg hover:border-gold/50 transition-colors flex items-center justify-center"
            title="테마 전환"
          >
            {theme === 'dark' ? '\u2600' : '\uD83C\uDF19'}
          </button>
        )}
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
