'use client'

import { useIntelData } from '@/hooks/useIntelData'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function scoreColor(score: number): string {
  if (score >= 0.8) return '#4dca7e'
  if (score >= 0.6) return '#c9a93a'
  return '#e09b3d'
}

export function DiscoveryTab() {
  const { data } = useIntelData()
  const opportunities = data?.opportunities?.opportunities ?? []  // 실제: data.opportunities.opportunities[]

  const chartData = opportunities.map(o => ({
    name: o.name ?? o.ticker,
    score: +((o.composite_score ?? 0) * 100).toFixed(1),
  }))

  return (
    <div className="space-y-4">
      {chartData.length > 0 && (
        <Card className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono">퀀트 스코어</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9a8e84' }} />
                <YAxis tick={{ fontSize: 10, fill: '#9a8e84' }} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: '#131210', border: '1px solid #2a2420' }} />
                <Bar dataKey="score" radius={[2, 2, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={scoreColor(entry.score / 100)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <Card className="bg-mc-card border-mc-border">
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-xs font-mono">발굴 종목</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-mc-border hover:bg-transparent">
                <TableHead className="text-xs text-muted-foreground">종목명</TableHead>
                <TableHead className="text-xs text-muted-foreground">티커</TableHead>
                <TableHead className="text-xs text-muted-foreground text-right">복합점수</TableHead>
                <TableHead className="text-xs text-muted-foreground">발굴 키워드</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {opportunities.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground text-xs py-6">
                    발굴 종목 없음
                  </TableCell>
                </TableRow>
              ) : (
                opportunities.map((o) => {
                  const score = (o.composite_score ?? 0) * 100
                  return (
                    <TableRow key={o.ticker} className="border-mc-border">
                      <TableCell className="text-xs font-medium">{o.name ?? '—'}</TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground">{o.ticker}</TableCell>
                      <TableCell className="text-xs text-right font-mono" style={{ color: scoreColor(o.composite_score ?? 0) }}>
                        {score.toFixed(0)}
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="flex flex-wrap gap-1">
                          {(o.keywords ?? []).slice(0, 3).map(k => (
                            <Badge key={k} variant="outline" className="text-[10px] border-mc-border">{k}</Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
