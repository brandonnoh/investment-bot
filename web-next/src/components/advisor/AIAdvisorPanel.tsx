'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { saveStrategy, type SavedLoan } from '@/lib/savedStrategies'
import type { InvestmentAsset, MinusLoanConfig, CreditLoanConfig, PortfolioMode } from '@/types/advisor'

const BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE
  ? process.env.NEXT_PUBLIC_API_BASE
  : ''

interface AIAdvisorPanelProps {
  capital: number
  minusLoan: MinusLoanConfig | null
  creditLoan: CreditLoanConfig | null
  monthlySavings: number
  riskLevel: number
  portfolioMode: PortfolioMode
  availableAssets: InvestmentAsset[]
}

export function AIAdvisorPanel({
  capital, minusLoan, creditLoan, monthlySavings, riskLevel, portfolioMode, availableAssets,
}: AIAdvisorPanelProps) {
  const [recommendation, setRecommendation] = useState<string | null>(null)
  const [streamText, setStreamText] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const logEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const fetchAdvice = useCallback(async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setLoading(true)
    setError(null)
    setRecommendation(null)
    setStreamText('')
    setLogs([])

    const leverageAmt = (minusLoan?.amount ?? 0) + (creditLoan?.amount ?? 0)
    const loans: SavedLoan[] = [
      ...(minusLoan && minusLoan.amount > 0
        ? [{ type: 'minus' as const, amount: minusLoan.amount, rate: minusLoan.rate }]
        : []),
      ...(creditLoan && creditLoan.amount > 0
        ? [{
            type: 'credit' as const,
            amount: creditLoan.amount,
            rate: creditLoan.rate,
            grace_period: creditLoan.gracePeriod,
            repay_period: creditLoan.repayPeriod,
          }]
        : []),
    ]

    try {
      const res = await fetch(`${BASE}/api/investment-advice-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capital,
          leverage_amt: leverageAmt,
          risk_level: riskLevel,
          monthly_savings: monthlySavings,
          portfolio_mode: portfolioMode,
          loans,
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
            reader.cancel().catch(() => {})  // 연결 정리
            setRecommendation(fullText)
            setStreamText('')
            setLoading(false)
            if (fullText) {
              saveStrategy(capital, leverageAmt, riskLevel, fullText, loans, monthlySavings)
            }
            return
          }
          try {
            const ev = JSON.parse(data) as { type?: string; msg?: string; text?: string }
            if (ev.type === 'log' && ev.msg) {
              setLogs(prev => [...prev, ev.msg ?? ''])
            } else if (ev.type === 'text' && ev.text) {
              fullText += ev.text
              setStreamText(fullText)
            } else if (ev.type === 'error' && ev.msg) {
              setError(ev.msg)
              setLoading(false)
              return
            }
          } catch { /* 불완전 JSON 청크 무시 */ }
        }
      }

      if (fullText) {
        setRecommendation(fullText)
        saveStrategy(capital, leverageAmt, riskLevel, fullText, loans, monthlySavings)
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setError(e instanceof Error ? e.message : '알 수 없는 오류')
    } finally {
      setLoading(false)
    }
  }, [capital, minusLoan, creditLoan, monthlySavings, riskLevel, portfolioMode, availableAssets])

  const displayText = loading ? streamText : recommendation

  return (
    <div className="rounded-md border border-mc-border bg-mc-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
          AI 투자 어드바이저
        </h3>
        <button
          onClick={fetchAdvice}
          disabled={loading}
          className="px-3 py-1.5 text-xs font-semibold rounded bg-gold text-black hover:bg-gold/80 disabled:opacity-40 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-1 focus-visible:ring-offset-mc-bg"
        >
          {loading ? '분석 중…' : '분석 갱신'}
        </button>
      </div>

      <div className="min-h-[100px] max-h-[600px] overflow-y-auto rounded bg-mc-bg border border-mc-border p-3">
        {loading && !streamText && (
          <div className="font-mono text-xs space-y-1 py-2">
            {logs.map((msg, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gold/60 shrink-0">{'>'}</span>
                <span className="text-muted-foreground">{msg}</span>
              </div>
            ))}
            <div className="flex gap-2">
              <span className="text-gold/60 shrink-0">{'>'}</span>
              <span className="text-gold animate-pulse">▌</span>
            </div>
            <div ref={logEndRef} />
          </div>
        )}

        {displayText && (
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

      {!loading && recommendation && (
        <p className="text-[10px] text-muted-foreground/50 font-mono text-right">
          ✓ 저장된 전략 탭에 자동 저장됨
        </p>
      )}
    </div>
  )
}
