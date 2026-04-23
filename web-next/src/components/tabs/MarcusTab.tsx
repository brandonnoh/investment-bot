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

/** 마크다운 컴포넌트 공통 정의 */
const MD_COMPONENTS = {
  h1: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="text-base font-bold text-gold font-mono mb-2 mt-0">{children}</h1>
  ),
  h2: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="text-sm font-semibold text-gold font-mono mb-1 mt-3">{children}</h2>
  ),
  h3: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="text-[10px] font-semibold text-gold/60 uppercase tracking-widest mb-2 mt-4">{children}</h3>
  ),
  p: ({ children }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="text-sm text-foreground mb-2 leading-relaxed">{children}</p>
  ),
  blockquote: ({ children }: React.HTMLAttributes<HTMLQuoteElement>) => (
    <div className="border-l-2 border-gold bg-gold/5 rounded-r px-3 py-2 my-2 text-sm text-foreground">
      {children}
    </div>
  ),
  ul: ({ children }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="space-y-1.5 my-2 list-none pl-0">{children}</ul>
  ),
  ol: ({ children }: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="space-y-1 my-2 list-decimal list-inside">{children}</ol>
  ),
  li: ({ children }: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="text-sm text-foreground leading-snug">{children}</li>
  ),
  hr: () => <hr className="border-mc-border my-3" />,
  strong: ({ children }: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: React.HTMLAttributes<HTMLElement>) => (
    <em className="italic text-muted-foreground">{children}</em>
  ),
  table: ({ children }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto my-3">
      <table className="w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th className="border border-mc-border px-2 py-1.5 text-left text-gold bg-mc-bg font-mono font-semibold">{children}</th>
  ),
  td: ({ children }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="border border-mc-border px-2 py-1.5 text-foreground">{children}</td>
  ),
  code: ({ children }: React.HTMLAttributes<HTMLElement>) => (
    <code className="text-gold bg-mc-bg px-1 rounded text-xs font-mono">{children}</code>
  ),
}

/** 마크다운에서 ticker 추출: **종목명** (TICKER, N점) 패턴 */
function extractTicker(line: string): string | null {
  const match = line.match(/\(([A-Z0-9.]+),/)
  return match ? match[1] : null
}

/** "### 눈여겨볼 종목" 섹션의 번호 항목 파싱 */
function parseWatchlistItems(md: string): Array<{ line: string; ticker: string | null }> {
  const sectionMatch = md.match(/###\s*눈여겨볼\s*종목([\s\S]*?)(?=\n###|\n---|\s*$)/)
  if (!sectionMatch) return []
  const sectionText = sectionMatch[1]
  return sectionText
    .split('\n')
    .filter((line) => /^\d+\./.test(line.trim()))
    .map((line) => ({ line: line.trim(), ticker: extractTicker(line) }))
}

/** 마크다운을 눈여겨볼 종목 섹션 기준으로 3분할 */
function splitMarkdown(md: string): { before: string; items: Array<{ line: string; ticker: string | null }>; after: string } {
  const sectionRe = /(###\s*눈여겨볼\s*종목)/
  const sectionIdx = md.search(sectionRe)
  if (sectionIdx === -1) return { before: md, items: [], after: '' }

  const before = md.slice(0, sectionIdx)
  const rest = md.slice(sectionIdx)

  // 다음 ### 또는 --- 위치 탐색
  const afterMatch = rest.match(/\n(###|---)/)
  const afterStart = afterMatch ? rest.indexOf(afterMatch[0]) : rest.length
  const after = rest.slice(afterStart)

  const items = parseWatchlistItems(rest.slice(0, afterStart))
  return { before, items, after }
}

/** 눈여겨볼 종목 섹션 헤더 */
function WatchlistHeader() {
  return (
    <h3 className="text-[10px] font-semibold text-gold/60 uppercase tracking-widest mb-2 mt-4">
      눈여겨볼 종목
    </h3>
  )
}

/** 개별 종목 줄 + 발굴 버튼 */
function WatchlistItem({ line, ticker, onJump }: { line: string; ticker: string | null; onJump: (t: string) => void }) {
  // 줄에서 마크다운 bold(**...**) 제거 후 텍스트로 표시
  const displayText = line.replace(/\*\*/g, '')
  return (
    <div className="flex items-start gap-2 py-0.5">
      <span className="flex-1 text-xs leading-relaxed text-foreground">{displayText}</span>
      {ticker && (
        <button
          onClick={() => onJump(ticker)}
          className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded border transition-colors"
          style={{
            borderColor: '#4dca7e',
            color: '#4dca7e',
            background: 'rgba(77,202,126,0.08)',
          }}
        >
          발굴에서 보기 →
        </button>
      )}
    </div>
  )
}

/** 마크다운 렌더러 */
function MdRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
      {content}
    </ReactMarkdown>
  )
}

/** 눈여겨볼 종목 섹션 포함 마크다운 렌더러 */
function MarcusMarkdown({ md, onJump }: { md: string; onJump: (ticker: string) => void }) {
  const { before, items, after } = splitMarkdown(md)

  return (
    <>
      {before && <MdRenderer content={before} />}
      {items.length > 0 && (
        <div className="mb-2">
          <WatchlistHeader />
          <div className="space-y-0.5">
            {items.map((item, i) => (
              <WatchlistItem key={i} line={item.line} ticker={item.ticker} onJump={onJump} />
            ))}
          </div>
        </div>
      )}
      {after && <MdRenderer content={after} />}
    </>
  )
}

export function MarcusTab() {
  const { data: intel } = useIntelData()
  const { history } = useAnalysisHistory()
  const { marcusRunning, jumpToDiscovery } = useMCStore()
  const logLines = useMarcusLog(marcusRunning)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [detail, setDetail] = useState<string | null>(null)

  const currentMd = detail ?? intel?.marcus_analysis ?? ''

  async function loadDetail(date: string) {
    setSelectedDate(date)
    try {
      const res = await fetch(`${BASE}/api/analysis-history?date=${date}`)
      if (!res.ok) throw new Error('fetch failed')
      const d = (await res.json()) as { content?: string; analysis?: string }
      setDetail(d?.content ?? d?.analysis ?? '')
    } catch (e) {
      console.warn('[MarcusTab] 분석 이력 로드 실패:', e)
      setDetail('')
    }
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[260px_1fr] xl:grid-cols-[320px_1fr] gap-4">
      {/* 사이드: 이력 목록 */}
      <div className="order-1 sm:order-1">
        <div className="text-xs text-muted-foreground font-mono mb-3">분석 이력</div>
        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground">이력 없음</p>
        ) : (
          <div className="flex gap-2 overflow-x-auto pb-1 sm:flex-col sm:overflow-visible sm:pb-0 sm:space-y-2">
            {history.map((h) => (
              <button
                key={h.date}
                onClick={() => { void loadDetail(h.date) }}
                className={`min-w-[120px] sm:min-w-0 sm:w-full text-left p-3 rounded border transition-colors shrink-0 sm:shrink ${
                  selectedDate === h.date
                    ? 'border-gold bg-gold/10'
                    : 'border-mc-border bg-mc-card hover:border-gold/40'
                }`}
              >
                <div className="font-mono text-xs font-semibold">{h.date}</div>
                <div className="flex gap-2 items-center mt-1">
                  {h.confidence_level !== undefined && (
                    <span className="text-[10px] text-gold">
                      {'★'.repeat(h.confidence_level)}
                    </span>
                  )}
                  <span className={`text-[10px] ${h.stance ? 'text-gold' : 'text-muted-foreground'}`}>
                    {h.stance ?? '—'}
                  </span>
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

      {/* 메인: 마크다운 결과 */}
      <Card className="bg-mc-card border-mc-border min-w-0 order-2 sm:order-2">
        <CardContent className="p-4">
          {marcusRunning ? (
            <div className="text-gold text-sm font-mono animate-pulse">
              AI 분석 실행 중...
            </div>
          ) : currentMd ? (
            <MarcusMarkdown md={currentMd} onJump={jumpToDiscovery} />
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
                    line.includes('✅') ? 'text-mc-green'
                    : line.includes('❌') ? 'text-mc-red'
                    : line.includes('⚠') ? 'text-amber-400'
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
    </div>
  )
}
