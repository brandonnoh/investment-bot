'use client'

import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Trash2, ChevronDown, ChevronUp, BookMarked } from 'lucide-react'
import {
  loadStrategies,
  deleteStrategy,
  parseLoans,
  fmtAmt,
  riskLabel,
  type SavedStrategy,
  type SavedLoan,
} from '@/lib/savedStrategies'

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function previewText(text: string): string {
  return text
    .replace(/^#+\s*/gm, '')
    .replace(/\*\*/g, '')
    .replace(/\n+/g, ' ')
    .trim()
    .slice(0, 120)
}

function ContextChip({ children, color = 'gold' }: { children: React.ReactNode; color?: 'gold' | 'red' | 'muted' }) {
  const cls = {
    gold: 'bg-gold/10 text-gold border-gold/20',
    red: 'bg-mc-red/10 text-mc-red border-mc-red/20',
    muted: 'bg-mc-border/20 text-muted-foreground border-mc-border',
  }[color]
  return (
    <span className={`inline-flex items-center text-[14px] px-1.5 py-0.5 rounded border font-mono ${cls}`}>
      {children}
    </span>
  )
}

function LoanChips({ loansJson }: { loansJson?: string }) {
  const loans: SavedLoan[] = parseLoans(loansJson)
  if (loans.length === 0) return null
  return (
    <>
      {loans.map((l, i) => (
        <ContextChip key={i} color="red">
          {l.type === 'minus' ? '마통' : '신용'} {fmtAmt(l.amount)} {l.rate}%
        </ContextChip>
      ))}
    </>
  )
}

function StrategyCard({
  strategy,
  onDelete,
}: {
  strategy: SavedStrategy
  onDelete: (id: number) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`rounded-lg border transition-colors ${expanded ? 'border-gold/30 bg-mc-card' : 'border-mc-border bg-mc-card hover:border-mc-border/80'}`}>
      <button
        className="w-full text-left p-4 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-inset rounded-lg"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[14px] text-muted-foreground font-mono">
                {formatDate(strategy.saved_at)}
              </span>
              <span className="text-muted-foreground/40 text-[14px]">·</span>
              <ContextChip>자본 {fmtAmt(strategy.capital)}</ContextChip>
              <LoanChips loansJson={strategy.loans_json} />
              {(!strategy.loans_json || strategy.loans_json === '[]') && strategy.leverage_amt > 0 && (
                <ContextChip color="red">대출 {fmtAmt(strategy.leverage_amt)}</ContextChip>
              )}
              {strategy.monthly_savings != null && strategy.monthly_savings > 0 && (
                <ContextChip color="muted">월 {fmtAmt(strategy.monthly_savings)}</ContextChip>
              )}
              <ContextChip color="muted">Lv.{strategy.risk_level} {riskLabel(strategy.risk_level)}</ContextChip>
            </div>
            {!expanded && (
              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                {previewText(strategy.recommendation)}…
              </p>
            )}
          </div>
          <div className="shrink-0 text-muted-foreground mt-0.5">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-mc-border">
          <div className="p-4 max-h-[600px] overflow-y-auto">
            <div className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed
              overflow-x-auto
              [&_p]:mb-3
              [&_strong]:text-foreground
              [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-foreground [&_h1]:mb-2 [&_h1]:mt-4
              [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-gold [&_h2]:mb-2 [&_h2]:mt-4
              [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-muted-foreground [&_h3]:mb-1.5 [&_h3]:mt-3 [&_h3]:uppercase [&_h3]:tracking-wider
              [&_ul]:list-none [&_ul]:pl-0 [&_li]:text-sm [&_li]:mb-1
              [&_table]:w-full [&_table]:text-xs [&_table]:block [&_table]:overflow-x-auto
              [&_th]:border [&_th]:border-mc-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-gold [&_th]:bg-mc-bg
              [&_td]:border [&_td]:border-mc-border [&_td]:px-2 [&_td]:py-1
              [&_hr]:border-mc-border [&_hr]:my-4
            ">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {strategy.recommendation}
              </ReactMarkdown>
            </div>
          </div>
          <div className="flex justify-end px-4 pb-3">
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(strategy.id) }}
              className="flex items-center gap-1.5 text-[14px] text-mc-red/60 hover:text-mc-red transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mc-red rounded px-2 py-1"
            >
              <Trash2 size={12} />
              삭제
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function SavedStrategiesTab() {
  const [strategies, setStrategies] = useState<SavedStrategy[]>([])

  useEffect(() => {
    loadStrategies().then(setStrategies)
  }, [])

  const handleDelete = useCallback(async (id: number) => {
    const ok = await deleteStrategy(id)
    if (ok) setStrategies(prev => prev.filter(s => s.id !== id))
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookMarked size={14} className="text-gold" />
          <h2 className="text-xs font-mono font-semibold text-muted-foreground tracking-wider uppercase">
            저장된 전략
          </h2>
          {strategies.length > 0 && (
            <span className="text-[14px] px-1.5 py-0.5 rounded-full bg-gold/10 text-gold border border-gold/20 font-mono">
              {strategies.length}
            </span>
          )}
        </div>
      </div>

      {strategies.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <BookMarked size={32} className="text-mc-border" />
          <p className="text-sm text-muted-foreground">저장된 전략이 없습니다.</p>
          <p className="text-xs text-muted-foreground/60">어드바이저 탭에서 AI 분석하면 자동으로 저장됩니다.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map(s => (
            <StrategyCard key={s.id} strategy={s} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
