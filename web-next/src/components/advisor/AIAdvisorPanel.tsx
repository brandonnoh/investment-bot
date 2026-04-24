'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { saveStrategy } from '@/lib/savedStrategies'
import type { InvestmentAsset } from '@/types/advisor'

const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

const STATUS_MESSAGES = [
  { at: 0,  msg: '시장 데이터 분석 중…' },
  { at: 15, msg: '자산 포트폴리오 검토 중…' },
  { at: 30, msg: '레버리지 시나리오 계산 중…' },
  { at: 50, msg: '단계별 전략 구성 중…' },
  { at: 70, msg: '수익률·현금흐름 추정 중…' },
  { at: 85, msg: '최종 로드맵 정리 중…' },
]

function statusMsgAt(progress: number) {
  return STATUS_MESSAGES.reduce((acc, s) => progress >= s.at ? s.msg : acc, STATUS_MESSAGES[0].msg)
}

interface AIAdvisorPanelProps {
  capital: number
  leverageAmt: number
  riskLevel: number
  availableAssets: InvestmentAsset[]
}

export function AIAdvisorPanel({
  capital, leverageAmt, riskLevel, availableAssets,
}: AIAdvisorPanelProps) {
  const [recommendation, setRecommendation] = useState<string | null>(null)
  const [streamText, setStreamText] = useState('')
  const [progress, setProgress] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 컴포넌트 언마운트 시 진행 중인 fetch 취소 (탭 전환 등)
  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  // 실제 스트림 데이터가 없는 동안 타이머로 가짜 진행률 표시 (Claude 응답 대기 중임을 알림)
  useEffect(() => {
    if (loading && !streamText) {
      timerRef.current = setInterval(() => {
        setProgress(prev => Math.min(85, prev + 1))
      }, 1500)
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [loading, streamText])

  const statusMsg = statusMsgAt(progress)

  const fetchAdvice = useCallback(async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setLoading(true)
    setError(null)
    setSaved(false)
    setRecommendation(null)
    setStreamText('')
    setProgress(0)

    try {
      const res = await fetch(`${BASE}/api/investment-advice-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capital,
          leverage_amt: leverageAmt,
          risk_level: riskLevel,
          available_assets: availableAssets,
        }),
        signal: ctrl.signal,
      })

      if (!res.ok || !res.body) throw new Error(`서버 오류: ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const data = line.slice(5).trim()
          if (data === '[DONE]') {
            setProgress(100)
            setRecommendation(fullText)
            setStreamText('')
            setLoading(false)
            return
          }
          try {
            const ev = JSON.parse(data) as { text?: string }
            if (ev.text) {
              fullText += ev.text
              setStreamText(fullText)
              setProgress(Math.min(95, Math.round(fullText.length / 6000 * 100)))
            }
          } catch { /* 불완전 JSON 청크 무시 */ }
        }
      }

      if (fullText) {
        setRecommendation(fullText)
        setProgress(100)
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setError(e instanceof Error ? e.message : '알 수 없는 오류')
    } finally {
      setLoading(false)
    }
  }, [capital, leverageAmt, riskLevel, availableAssets])

  const handleSave = useCallback(() => {
    if (!recommendation) return
    saveStrategy({ capital, leverageAmt, riskLevel, recommendation })
    setSaved(true)
  }, [recommendation, capital, leverageAmt, riskLevel])

  const displayText = loading ? streamText : recommendation

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
          AI 투자 어드바이저
        </h3>
        <div className="flex items-center gap-2">
          {recommendation && !loading && (
            <button
              onClick={handleSave}
              disabled={saved}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg disabled:cursor-default ${
                saved
                  ? 'bg-gold/10 border-gold/30 text-gold'
                  : 'bg-transparent border-mc-border text-muted-foreground hover:border-gold/40 hover:text-gold'
              }`}
            >
              {saved ? <BookmarkCheck size={12} /> : <Bookmark size={12} />}
              {saved ? '저장됨' : '저장'}
            </button>
          )}
          <button
            onClick={fetchAdvice}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold rounded bg-gold text-black hover:bg-gold/80 disabled:opacity-40 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg"
          >
            {loading ? '분석 중…' : '분석 갱신'}
          </button>
        </div>
      </div>

      <div className="min-h-[100px] max-h-[600px] overflow-y-auto rounded bg-mc-bg border border-mc-border p-3">
        {/* 텍스트 없이 로딩 중 — 중앙 퍼센트 UI */}
        {loading && !streamText && (
          <div className="flex flex-col items-center justify-center gap-4 py-8">
            <div className="text-3xl font-mono font-bold text-gold tabular-nums">
              {progress}<span className="text-lg text-gold/60">%</span>
            </div>
            <div className="w-full max-w-xs h-1.5 rounded-full bg-mc-border overflow-hidden">
              <div
                className="h-full rounded-full bg-gold transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground font-mono animate-pulse">{statusMsg}</p>
          </div>
        )}

        {/* 스트리밍 중 + 완료 후 텍스트 */}
        {displayText && (
          <>
            {loading && (
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 h-1 rounded-full bg-mc-border overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gold transition-all duration-300 ease-out"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-gold tabular-nums shrink-0">{progress}%</span>
              </div>
            )}
            <div className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed
              overflow-x-auto
              [&_p]:mb-2 [&_strong]:text-foreground
              [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-foreground [&_h1]:mb-2 [&_h1]:mt-3
              [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-gold [&_h2]:mb-1.5 [&_h2]:mt-3
              [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-muted-foreground [&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:uppercase [&_h3]:tracking-wider
              [&_table]:w-full [&_table]:text-xs [&_table]:block [&_table]:overflow-x-auto
              [&_th]:border [&_th]:border-mc-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-gold [&_th]:bg-mc-bg
              [&_td]:border [&_td]:border-mc-border [&_td]:px-2 [&_td]:py-1
              [&_ul]:list-none [&_ul]:pl-0 [&_li]:text-sm [&_hr]:border-mc-border [&_hr]:my-3
            ">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayText}
              </ReactMarkdown>
            </div>
          </>
        )}

        {!loading && error && (
          <div className="text-xs text-mc-red">오류: {error}</div>
        )}
        {!loading && !error && !recommendation && (
          <p className="text-xs text-muted-foreground">
            &quot;분석 갱신&quot; 버튼을 눌러 AI 투자 추천을 받아보세요.
          </p>
        )}
      </div>
    </div>
  )
}
