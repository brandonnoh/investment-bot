import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface ServiceItem {
  name: string
  desc: string
  output?: string
}

interface ServiceSection {
  title: string
  icon: string
  items: ServiceItem[]
}

const SERVICE_MAP: ServiceSection[] = [
  {
    title: '수집 계층',
    icon: '\u2B21',
    items: [
      { name: 'fetch_prices.py', desc: '주가 수집 (Yahoo Finance)', output: 'prices.json' },
      { name: 'fetch_macro.py', desc: '거시지표 수집', output: 'macro.json' },
      { name: 'fetch_news.py', desc: '뉴스 수집 (RSS + Brave)', output: 'news DB' },
      { name: 'fetch_fundamentals.py', desc: '재무제표 (DART + Yahoo)' },
      { name: 'fetch_supply.py', desc: 'KRX 수급 + Fear&Greed', output: 'supply_data.json' },
      { name: 'fetch_opportunities.py', desc: '키워드 기반 종목 발굴', output: 'opportunities.json' },
    ],
  },
  {
    title: '분석 계층',
    icon: '\u25C8',
    items: [
      { name: 'alerts.py', desc: '임계값 알림 생성', output: 'alerts.json' },
      { name: 'screener.py', desc: '종목 스크리너' },
      { name: 'composite_score.py', desc: '6팩터 퀀트 스코어링' },
      { name: 'sentiment.py', desc: '뉴스 감성 분석' },
      { name: 'performance.py', desc: '성과 추적 + 가중치 학습', output: 'performance_report.json' },
    ],
  },
  {
    title: '배치/리포트',
    icon: '\u25C9',
    items: [
      { name: 'daily.py', desc: '일간 리포트 생성', output: 'daily.md' },
      { name: 'weekly.py', desc: '주간 리포트 생성', output: 'weekly.md' },
      { name: 'closing.py', desc: '장마감 리포트', output: 'closing.md' },
      { name: 'run_pipeline.py', desc: '전체 파이프라인 오케스트레이터' },
    ],
  },
  {
    title: 'DB 스키마',
    icon: '\u229E',
    items: [
      { name: 'prices', desc: '10분 해상도 주가 (3개월)', output: 'prices_daily' },
      { name: 'macro', desc: '거시지표 원시 + 일봉', output: 'macro_daily' },
      { name: 'news', desc: '뉴스 + 감성 분석 결과' },
      { name: 'alerts', desc: '알림 이력' },
      { name: 'portfolio_history', desc: '포트폴리오 일별 스냅샷' },
    ],
  },
  {
    title: '알림/연동',
    icon: '\u25EC',
    items: [
      { name: 'discord_notify.py', desc: 'Discord 비서실/재테크 알림' },
      { name: 'run_marcus.py', desc: 'Claude CLI Marcus 에이전트' },
      { name: 'web/server.py', desc: 'Flask 대시보드 서버', output: ':8421' },
      { name: 'web/api.py', desc: 'REST API 엔드포인트' },
    ],
  },
]

export function ServiceMapTab() {
  return (
    <div className="grid grid-cols-3 lg:grid-cols-2 sm:grid-cols-1 gap-4">
      {SERVICE_MAP.map(section => (
        <Card key={section.title} className="bg-mc-card border-mc-border">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-xs font-mono flex items-center gap-2">
              <span>{section.icon}</span>
              <span>{section.title}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="space-y-2">
              {section.items.map(item => (
                <div key={item.name} className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gold">{item.name}</span>
                    {item.output && (
                      <span className="text-[10px] text-muted-foreground">{'\u2192'} {item.output}</span>
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground">{item.desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
