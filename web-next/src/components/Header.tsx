'use client'

import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { useMCStore } from '@/store/useMCStore'
import { useProcessStatus } from '@/hooks/useProcessStatus'
import { useIntelData } from '@/hooks/useIntelData'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

function SpinnerIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`w-3.5 h-3.5 ${spinning ? 'animate-spin' : ''}`}
    >
      {spinning ? (
        <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
      ) : (
        <path d="M5 3l14 9-14 9V3z" />
      )}
    </svg>
  )
}

function MarcusIcon({ spinning }: { spinning: boolean }) {
  if (spinning) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 animate-spin">
        <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
      </svg>
    )
  }
  return <span className="text-sm leading-none">✦</span>
}

function useCompletionToast(running: boolean, label: string) {
  const prevRef = useRef<boolean>(false)
  useEffect(() => {
    if (prevRef.current && !running) {
      toast.success(`${label} 완료`)
    }
    prevRef.current = running
  }, [running, label])
}

export function Header() {
  const { pipelineRunning, marcusRunning, sseStatus, lastUpdated, setPipelineRunning, setMarcusRunning } = useMCStore()
  const { pipelineRunning: pipelineActive, marcusRunning: marcusActive } = useProcessStatus()
  const { data } = useIntelData()

  const isRunningPipeline = pipelineRunning || pipelineActive
  const isRunningMarcus = marcusRunning || marcusActive

  useCompletionToast(isRunningPipeline, '파이프라인')
  useCompletionToast(isRunningMarcus, 'AI 분석')

  const lastUpdatedLabel = (() => {
    // SSE 로컬 시각 우선: SWR 재검증 레이스 영향 없음, 항상 최신
    if (lastUpdated) return lastUpdated + ' 기준'
    const ts = data?.last_updated ?? data?.engine_status?.updated_at
    if (ts) {
      try {
        return new Date(ts).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) + ' 기준'
      } catch { /* fallback */ }
    }
    return null
  })()

  async function handleRunPipeline() {
    if (isRunningPipeline) return
    setPipelineRunning(true)
    toast.info('파이프라인 시작됨')
    try {
      const res = await fetch(`${BASE}/api/run-pipeline`, { method: 'POST' })
      const json = await res.json()
      if (!json.ok) {
        toast.error(`실행 실패: ${json.error ?? '알 수 없는 오류'}`)
      }
    } catch {
      toast.error('파이프라인 요청 실패')
    } finally {
      setPipelineRunning(false)
    }
  }

  async function handleRunMarcus() {
    if (isRunningMarcus) return
    setMarcusRunning(true)
    toast.info('AI 분석 시작됨')
    try {
      const res = await fetch(`${BASE}/api/run-marcus`, { method: 'POST' })
      const json = await res.json()
      if (!json.ok) {
        toast.error(`실행 실패: ${json.error ?? '알 수 없는 오류'}`)
      }
    } catch {
      toast.error('AI 분석 요청 실패')
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
          <span className="text-xs text-muted-foreground">{lastUpdatedLabel}</span>
        )}
      </div>
      <div />
    </header>
  )
}
