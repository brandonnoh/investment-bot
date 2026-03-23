# Investment Intelligence Bot — Claude 개발 가이드

## 프로젝트 개요
AI 에이전트(자비스, OpenClaw)가 읽을 투자 데이터 수집/분석 파이프라인.
**프로그램이 정확한 데이터를 처리하고, AI는 해석/판단/대화에 집중**하는 구조.

## 핵심 원칙

### 1. 데이터 품질 최우선
- Yahoo Finance API 실패 시 반드시 graceful fallback (예외 처리 필수)
- 모든 가격 데이터는 timestamp와 함께 저장
- DB와 JSON 출력 항상 동기화

### 2. 자비스 친화적 출력
- `output/intel/` 폴더가 자비스(AI)가 읽는 유일한 인터페이스
- 마크다운 리포트는 **한국어**로, 이모지 포함, 간결하게
- JSON 출력은 자비스가 파싱하기 쉽게 구조화

### 3. 코드 스타일
- 모든 주석은 **한국어**
- 함수마다 docstring 필수
- 각 모듈은 `run()` 함수를 진입점으로 노출
- 에러는 로그 출력 후 계속 진행 (전체 파이프라인 중단 금지)

### 4. 포트폴리오 변경은 config.py만
- 종목 추가/수정은 반드시 `config.py`의 `PORTFOLIO` 리스트만 수정
- 다른 파일에 하드코딩 절대 금지

## 디렉토리 구조
```
investment-bot/
├── config.py              # 포트폴리오, 임계값, 경로 설정
├── run_pipeline.py        # 전체 파이프라인 실행 진입점
├── data/
│   ├── fetch_prices.py    # 주가 수집 (Yahoo Finance)
│   └── fetch_macro.py     # 매크로 지표 수집
├── analysis/
│   ├── alerts.py          # 알림 감지
│   ├── screener.py        # 종목 발굴 (Phase 2)
│   └── portfolio.py       # 리스크 계산 (Phase 2)
├── reports/
│   ├── daily.py           # 일일 리포트
│   └── weekly.py          # 주간 리포트 (Phase 2)
├── db/
│   ├── init_db.py         # SQLite 스키마 초기화
│   └── history.db         # 가격 이력 (git 제외)
└── output/intel/          # 자비스가 읽는 폴더 (git 제외)
    ├── daily_report.md
    ├── prices.json
    ├── macro.json
    └── alerts.json
```

## 현재 개발 단계

### ✅ Phase 1 (완료)
- [x] config.py — 포트폴리오/설정
- [x] fetch_prices.py — 실시간 주가 수집 + DB
- [x] fetch_macro.py — 매크로 지표 수집 + DB
- [x] alerts.py — 알림 감지
- [x] daily.py — 일일 리포트
- [x] run_pipeline.py — 파이프라인 실행기

### 🔲 Phase 2 (다음)
- [ ] fetch_news.py — 뉴스 수집 (Brave Search API)
- [ ] screener.py — 신규 종목 발굴
- [ ] portfolio.py — 리스크/리밸런싱 계산
- [ ] weekly.py — 주간 리포트

### 🔲 Phase 3 (심화)
- [ ] 백테스트 모듈
- [ ] 차트 이미지 생성 (텔레그램 전송용)
- [ ] 증권사 API 자동매매 연동

## 포트폴리오 현황 (config.py 참조)
| 종목 | 티커 | 평단 | 수량 |
|------|------|------|------|
| 삼성전자 | 005930.KS | 203,102원 | 42주 |
| 현대차 | 005380.KS | 519,000원 | 9주 |
| TIGER 코리아AI전력기 | 0117V0.KS | 16,795원 | 60주 |
| TIGER 미국방산TOP10 | 458730.KS | 15,485원 | 64주 |
| 테슬라 | TSLA | $394.32 | 1주 |
| 알파벳 | GOOGL | $308.27 | 2주 |
| SPDR S&P Oil | XOP | $178.26 | 1주 |
| 금 현물 | GC=F | — | 128g |

## 알림 임계값
| 이벤트 | 임계값 | 레벨 |
|--------|--------|------|
| 종목 급락 | -5% | 🔴 긴급 |
| 종목 급등 | +5% | 🟢 알림 |
| 코스피 폭락 | -3% | 🔴 긴급 |
| 환율 급등 | 1,550원 | 🔴 긴급 |
| 유가 급등 | +5% | 🟡 주의 |
| 금 급변 | ±3% | 🟡 주의 |

## 실행 방법
```bash
# 전체 파이프라인 한 번 실행
python3 run_pipeline.py

# 개별 모듈 실행
python3 data/fetch_prices.py
python3 data/fetch_macro.py
python3 analysis/alerts.py
python3 reports/daily.py

# 의존성 설치
pip3 install -r requirements.txt
```

## 자비스(OpenClaw) 연동
- 맥미니 경로: `~/Desktop/investment-bot/output/intel/`
- 자비스 크론(05:00): `python3 run_pipeline.py` 실행
- 자비스 크론(05:30): `output/intel/daily_report.md` 읽어서 분석
- 자비스 크론(07:30): 모닝 브리핑에 포함해서 텔레그램 전송
- 알림 발생 시: `alerts.json` 존재하면 즉시 텔레그램 전송

## 환경 변수 (필요 시)
```bash
BRAVE_API_KEY=xxx   # Phase 2 뉴스 수집용
```

## 주의사항
- `db/history.db` — git에서 제외 (.gitignore)
- `output/` — git에서 제외 (.gitignore)
- Yahoo Finance 과도한 요청 시 rate limit 주의 (10분 간격 권장)
