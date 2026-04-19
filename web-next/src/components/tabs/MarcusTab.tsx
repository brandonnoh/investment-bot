'use client'

import { useState } from 'react'
import { useAnalysisHistory } from '@/hooks/useAnalysisHistory'
import { useIntelData } from '@/hooks/useIntelData'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useMCStore } from '@/store/useMCStore'
import { useMarcusLog } from '@/hooks/useMarcusLog'

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? ''

export function MarcusTab() {
  const { data: intel } = useIntelData()
  const { history } = useAnalysisHistory()
  const { marcusRunning } = useMCStore()
  const logLines = useMarcusLog(marcusRunning)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [detail, setDetail] = useState<string | null>(null)

  const currentMd = detail ?? intel?.marcus_analysis ?? ''

  async function loadDetail(date: string) {
    setSelectedDate(date)
    try {
      const res = await fetch(`${BASE}/api/analysis-history?date=${date}`)
      if (!res.ok) throw new Error('fetch failed')
      const d = (await res.json()) as { analysis?: string }
      setDetail(d?.analysis ?? '')
    } catch {
      setDetail('')
    }
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[280px_1fr] gap-4">
      {/* 메인: 마크다운 결과 */}
      <Card className="bg-mc-card border-mc-border min-w-0 order-2 sm:order-2">
        <CardContent className="p-4">
          {marcusRunning ? (
            <div className="text-gold text-sm font-mono animate-pulse">
              AI 분석 실행 중...
            </div>
          ) : currentMd ? (
            <div
              className="prose prose-invert prose-sm max-w-none text-foreground
              prose-headings:text-gold prose-headings:font-mono
              prose-strong:text-foreground
              prose-code:text-gold prose-code:bg-mc-bg prose-code:px-1 prose-code:rounded
              prose-blockquote:border-l-gold prose-blockquote:text-muted-foreground"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="w-full text-xs border-collapse">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-mc-border px-2 py-1 text-left text-gold bg-mc-bg font-mono">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-mc-border px-2 py-1">{children}</td>
                  ),
                }}
              >{currentMd}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              분석 결과 없음 — 헤더의 AI 분석 버튼을 눌러 실행하세요.
            </p>
          )}
        </CardContent>
      </Card>

      {/* 라이브 로그 뷰어 */}
      {marcusRunning && logLines.length > 0 && (
        <Card className="bg-mc-card border-mc-border mt-4 order-3 col-span-full">
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-xs font-mono">라이브 로그</CardTitle>
          </CardHeader>
          <CardContent className="px-3 pb-3">
            <div className="font-mono text-xs space-y-0.5 max-h-48 overflow-y-auto">
              {logLines.map((line, i) => (
                <div
                  key={i}
                  className={
                    line.includes('\u2705')
                      ? 'text-mc-green'
                      : line.includes('\u274C')
                        ? 'text-mc-red'
                        : line.includes('\u26A0')
                          ? 'text-amber-400'
                          : 'text-muted-foreground'
                  }
                >
                  {line}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 사이드: 이력 목록 */}
      <div className="order-1 sm:order-1">
        <div className="text-xs text-muted-foreground font-mono mb-3">
          분석 이력
        </div>
        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground">이력 없음</p>
        ) : (
          <div className="flex gap-2 overflow-x-auto pb-1 sm:flex-col sm:overflow-visible sm:pb-0 sm:space-y-2">
            {history.map((h) => (
              <button
                key={h.date}
                onClick={() => {
                  void loadDetail(h.date)
                }}
                className={`min-w-[120px] sm:min-w-0 sm:w-full text-left p-3 rounded border transition-colors shrink-0 sm:shrink ${
                  selectedDate === h.date
                    ? 'border-gold bg-gold/8'
                    : 'border-mc-border bg-mc-card hover:border-gold/30'
                }`}
              >
                <div className="font-mono text-xs font-semibold">{h.date}</div>
                <div className="flex gap-2 items-center mt-1">
                  {h.confidence_level !== undefined && (
                    <span className="text-[10px] text-gold">
                      {'★'.repeat(h.confidence_level)}
                    </span>
                  )}
                  {h.stance && (
                    <span className="text-[10px] text-muted-foreground">
                      {h.stance}
                    </span>
                  )}
                </div>
                {h.today_call && (
                  <div className="text-[11px] text-muted-foreground mt-1 line-clamp-2 hidden sm:block">
                    {h.today_call}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
