# Phase 4 논의 메모 — 종목 발굴 고도화

> 작성: 자비스 | 2026-03-25
> 상태: 논의 완료, 개발 예정

---

## 핵심 방향

**AI가 키워드를 그때그때 추론 → Python이 실행**

```
자비스 (05:30)
  → macro.json + news.json + price_analysis.json 읽기
  → "오늘 시장 환경에서 발굴할 키워드 5개 추론"
  → DB 저장 (opportunity_keywords 테이블)
  → python3 fetch_opportunities.py 실행
  → Brave Search로 뉴스 검색
  → 후보 종목 DB 저장 (opportunity_results 테이블)
  → screener.py 기술 분석으로 최종 선별
  → 자비스 종합 판단 → 텔레그램
```

---

## 신규 DB 테이블

```sql
-- AI가 추론한 발굴 키워드
CREATE TABLE opportunity_keywords (
    id INTEGER PRIMARY KEY,
    date TEXT,                    -- 2026-03-25
    keyword TEXT,                 -- "한화에어로스페이스 수주"
    reason TEXT,                  -- AI 추론 근거
    macro_context TEXT,           -- 당시 매크로 상황 요약
    created_at TEXT
);

-- 키워드로 발굴된 종목 후보
CREATE TABLE opportunity_results (
    id INTEGER PRIMARY KEY,
    keyword_id INTEGER,
    ticker TEXT,
    name TEXT,
    score REAL,                   -- 복합 점수
    reason TEXT,
    created_at TEXT,
    FOREIGN KEY (keyword_id) REFERENCES opportunity_keywords(id)
);
```

> 키워드를 JSON 파일 대신 DB에 저장 — 이력 추적, 백테스트, 중복 방지 위해

---

## 개발 목록

### F16. fetch_opportunities.py (신규)
- opportunity_keywords 테이블에서 오늘 키워드 읽기
- Brave Search API로 검색
- 결과 파싱 → opportunity_results 저장
- output/intel/opportunities.json 생성

### F17. screener.py 고도화
- 기존: 15개 고정 × 1개월 수익률
- 개선: 복합 점수 = 수익률×0.3 + RSI×0.3 + 뉴스감성×0.2 + 매크로방향×0.2
- 유니버스 확장 (50~100개 종목)
- opportunities.json 결과 통합

### F18. 뉴스 수집 목적 분리
- fetch_news.py → 보유 종목 모니터링 전용 (현재 유지)
- fetch_opportunities.py → 신규 발굴 전용

---

## 자비스 05:30 파이프라인 변경

```
기존:
  데이터 읽기 → 분석 → CIO 보고서

변경:
  데이터 읽기
  → 발굴 키워드 추론 (AI) → DB 저장
  → fetch_opportunities.py 실행
  → screener.py 실행 (opportunities 통합)
  → CIO 보고서 (발굴 섹션 추가)
```

---

## 추후 논의 필요

- Google Trends API 연동 가능성
- 자동매매 연동 (Phase 5 이후)
- Mission Control 대시보드
