'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
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

function useAnalysisProgress(loading: boolean) {
  const [progress, setProgress] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!loading) {
      if (timerRef.current) clearInterval(timerRef.current)
      setProgress(0)
      return
    }

    setProgress(0)
    const start = Date.now()

    timerRef.current = setInterval(() => {
      const elapsed = (Date.now() - start) / 1000
      // 0→40%: 빠르게(20s), 40→75%: 보통(30s), 75→92%: 느리게(무한 수렴)
      let p: number
      if (elapsed < 20) p = (elapsed / 20) * 40
      else if (elapsed < 50) p = 40 + ((elapsed - 20) / 30) * 35
      else p = 75 + (1 - Math.exp(-(elapsed - 50) / 40)) * 17
      setProgress(Math.min(92, Math.round(p)))
    }, 300)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [loading])

  const statusMsg = STATUS_MESSAGES.reduce((acc, s) => progress >= s.at ? s.msg : acc, STATUS_MESSAGES[0].msg)
  return { progress, statusMsg }
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const { progress, statusMsg } = useAnalysisProgress(loading)

  const fetchAdvice = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSaved(false)
    try {
      const res = await fetch(`${BASE}/api/investment-advice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capital,
          leverage_amt: leverageAmt,
          risk_level: riskLevel,
          available_assets: availableAssets,
        }),
      })
      if (!res.ok) throw new Error(`서버 오류: ${res.status}`)
      const data = await res.json()
      setRecommendation(data.recommendation ?? '추천 결과 없음')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '알 수 없는 오류'
      setError(msg)
      setRecommendation(null)
    } finally {
      setLoading(false)
    }
  }, [capital, leverageAmt, riskLevel, availableAssets])

  const handleSave = useCallback(() => {
    if (!recommendation) return
    saveStrategy({ capital, leverageAmt, riskLevel, recommendation })
    setSaved(true)
  }, [recommendation, capital, leverageAmt, riskLevel])

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

      {/* 추천 영역 */}
      <div className="min-h-[100px] max-h-[600px] overflow-y-auto rounded bg-mc-bg border border-mc-border p-3">
        {loading && (
          <div className="flex flex-col items-center justify-center gap-4 py-8">
            {/* 퍼센트 */}
            <div className="text-3xl font-mono font-bold text-gold tabular-nums">
              {progress}<span className="text-lg text-gold/60">%</span>
            </div>
            {/* 프로그레스 바 */}
            <div className="w-full max-w-xs h-1.5 rounded-full bg-mc-border overflow-hidden">
              <div
                className="h-full rounded-full bg-gold transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            {/* 상태 메시지 */}
            <p className="text-xs text-muted-foreground font-mono animate-pulse">{statusMsg}</p>
          </div>
        )}
        {!loading && error && (
          <div className="text-xs text-mc-red">오류: {error}</div>
        )}
        {!loading && !error && recommendation && (
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
              {recommendation}
            </ReactMarkdown>
          </div>
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
