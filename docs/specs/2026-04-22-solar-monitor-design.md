# 태양광 발전소 매물 모니터링 — 설계 문서

작성일: 2026-04-22

## 개요

9개 태양광 발전소 거래 사이트를 하루 2회 크롤링하여 신규 매물을 DB에 저장하고, Discord 알림 + 대시보드 탭으로 노출한다.

## 모니터링 대상 사이트

| ID | 사이트명 | URL |
|----|--------|-----|
| allthatsolar | 올댓솔라 | allthatsolar.com |
| solarmarket | 솔라마켓 | solar-market.co.kr |
| exchange | 태양광발전거래소 | xn--v69ayl04xcue64hjogqven8v.com |
| solartrade | 솔라트레이드 | solartrade.co.kr |
| solardirect | 솔라다이렉트 | solardirect.co.kr |
| haetbit | 햇빛길 플러스 | haetbit-gil.com |
| ssunlab | 썬랩 | ssunlab.com |
| koreari | 한국태양광연구소 | koreari.org |
| onbid | 온비드 | onbid.co.kr |

## 아키텍처

```
scripts/refresh_solar.py         ← cron 진입점 (아침 08:30, 저녁 19:00 KST)

data/
  fetch_solar_base.py            ← B→A 폴백 공통 로직
  fetch_solar_allthatsolar.py
  fetch_solar_solarmarket.py
  fetch_solar_exchange.py
  fetch_solar_solartrade.py
  fetch_solar_solardirect.py
  fetch_solar_haetbit.py
  fetch_solar_ssunlab.py
  fetch_solar_koreari.py
  fetch_solar_onbid.py

analysis/solar_alerts.py         ← 신규 매물 감지 + Discord 알림

web/api.py                       ← load_solar_listings() 추가
web/server.py                    ← GET /api/solar 라우트 추가
crontab.docker                   ← 스케줄 추가

web-next/src/
  types/api.ts                   ← SolarListing 타입
  store/useMCStore.ts            ← 'solar' TabId 추가
  components/TabNav.tsx          ← 태양광 탭 추가 (EXTRA_TABS)
  components/tabs/SolarTab.tsx   ← 매물 카드 리스트
  app/page.tsx                   ← SolarTab 렌더링 추가
```

## DB 스키마

```sql
CREATE TABLE IF NOT EXISTS solar_listings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  listing_id    TEXT NOT NULL,
  title         TEXT,
  capacity_kw   REAL,
  location      TEXT,
  price_krw     INTEGER,
  url           TEXT,
  status        TEXT DEFAULT 'active',
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  raw_json      TEXT,
  UNIQUE(source, listing_id)
);
```

## 크롤러 폴백 전략

1. **B (JSON API)**: 개발자도구로 역공학한 내부 REST API 직접 호출
2. **A (HTML 파싱)**: urllib + 정규식으로 HTML에서 목록 추출
3. 둘 다 실패 시 빈 리스트 반환 (Playwright은 추후)

## 신규 매물 감지

```
run() → 9개 크롤러 순차 실행 → 전체 매물 수집
      → INSERT OR IGNORE → rowcount > 0 = 신규
      → 신규만 Discord 전송
      → 기존은 last_seen_at 업데이트
```

## Discord 알림 포맷

```
🌞 새 태양광 매물 — 솔라마켓
경남 고성군 100kW | 1억 2,000만원
→ https://solar-market.co.kr/...
```

채널: 재테크 알림 (1486921732874047629)

## 크론 스케줄

```
30  8 * * * refresh_solar.py   # 매일 08:30 KST
0  19 * * * refresh_solar.py   # 매일 19:00 KST
```

## 대시보드 탭

- EXTRA_TABS에 추가 (더보기 메뉴)
- 최신순 매물 카드 리스트
- 카드: 출처 배지 + 제목 + 지역 + 용량 + 가격 + 발견일 + 원본링크
- 오늘 신규 매물 강조 표시
