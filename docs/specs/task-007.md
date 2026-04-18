# task-007: 발굴 탭 + 알림 탭 + 시스템 탭 + 서비스 맵 탭

## 배경
나머지 4개 탭 구현. 각 탭은 독립적이며 useIntelData 훅 데이터 사용.

## 구현 방향

### DiscoveryTab.tsx
```typescript
// data.opportunities 배열 렌더링
// 컬럼: 종목명 / 티커 / 복합점수(0~1→ 0~100) / 발굴 키워드
// 점수 색상: ≥80 green, ≥60 gold, else amber
// shadcn Table + Badge

// 퀀트 스코어 Bar (Recharts BarChart)
// x=종목명, y=composite_score*100, fill에 점수별 색상
```

### AlertsTab.tsx
```typescript
// data.alerts.alerts 배열 렌더링
// level별 스타일:
//   critical → border-l-4 border-mc-red bg-mc-red/5
//   warning  → border-l-4 border-amber bg-amber/5
//   info     → border-l-4 border-mc-border
// shadcn Badge로 level 표시
// 빈 알림 시: "현재 활성 알림이 없습니다" 표시
```

### SystemTab.tsx
```typescript
// data.engine_status 렌더링
// 엔진 상태 카드:
//   - 마지막 수집: engine_status.last_run (상대 시간)
//   - 에러 횟수: engine_status.error_count
//   - DB 용량: engine_status.db_size_mb MB
// intel 파일 그리드:
//   - engine_status.intel_files 배열 → 파일명/크기 배지 형태
//   - .md 파일은 gold 강조
```

### ServiceMapTab.tsx
현재 web/index.html 서비스 맵 탭(줄 ~900 이후)과 동일한 정적 데이터:
```typescript
// 3컬럼 그리드 (lg:2, sm:1)
// 카드 5개: 수집 / 분석 / 배치 / 리포트 / DB 스키마
// 각 카드: 섹션명 + 파일 목록 (파일명 + 설명)
// 완전히 정적 데이터 — API 불필요
const SERVICE_MAP = [
  {
    title: '수집 계층',
    icon: 'DatabaseIcon',
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
    icon: 'ActivityIcon',
    items: [
      { name: 'alerts.py', desc: '임계값 알림 생성', output: 'alerts.json' },
      { name: 'screener.py', desc: '종목 스크리너' },
      { name: 'composite_score.py', desc: '6팩터 퀀트 스코어링' },
      { name: 'sentiment.py', desc: '뉴스 감성 분석' },
      { name: 'performance.py', desc: '성과 추적 + 가중치 학습', output: 'performance_report.json' },
    ],
  },
  // ... 나머지
]
```

## 검증
```bash
cd web-next && npm run build
```
