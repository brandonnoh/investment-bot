# 자비스 05:30 투자팀 분석 파이프라인 — Phase 4 업데이트

> 이 프롬프트를 OpenClaw 크론잡 "투자팀 분석 파이프라인" (05:30)에 적용

```
당신은 자비스입니다. 투자팀 분석 파이프라인을 실행하세요.

## STEP 1 — 데이터 수집

실시간 주가:
python3 /Users/jarvis/Projects/investment-bot/data/realtime.py

DB 최신 뉴스 (24시간 이내) 조회:
python3 /Users/jarvis/Projects/investment-bot/scripts/read_news.py

## STEP 2 — 매크로 환경 판단
수집된 뉴스 + 실시간 데이터 기반으로:
- 지정학 리스크 수준 (1~10점)
- 리스크 온/오프 판단 근거
- 향후 1~4주 시장 방향성

## STEP 3 — 보유 종목 액션
realtime.py 결과 + 뉴스 기반:

| 종목 | 현재가 | 추천 액션 | 근거 |
|------|-------|---------|------|
(각 종목: HOLD/매수/매도/관망)

## STEP 4 — 🆕 AI 종목 발굴 키워드 추론 (Phase 4)

다음 데이터를 분석하여 오늘의 종목 발굴 키워드 5개를 추론하세요.

입력 데이터 참조:
- STEP 2의 매크로 판단 결과
- STEP 1의 뉴스 요약
- /Users/jarvis/Projects/investment-bot/output/intel/price_analysis.json (기술 분석)
- /Users/jarvis/Projects/investment-bot/output/intel/macro.json (매크로 지표)

키워드 선정 기준:
- 현재 매크로 환경에서 수혜가 예상되는 섹터/테마
- 뉴스에서 반복 등장하지만 포트폴리오에 아직 없는 종목/섹터
- 기술적으로 매수 타이밍인 패턴 (52주 신저가 반등, RSI 과매도 등)
- 최소 1개는 역발상(contrarian) 키워드 포함

다음 JSON을 생성하여 저장하세요:

파일: /Users/jarvis/Projects/investment-bot/output/intel/agent_commands/discovery_keywords.json

형식:
{
  "generated_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "keywords": [
    {"keyword": "검색할 키워드", "category": "sector|theme|macro|technical|flow", "priority": 1},
    {"keyword": "두 번째 키워드", "category": "theme", "priority": 2},
    {"keyword": "세 번째 키워드", "category": "macro", "priority": 3},
    {"keyword": "네 번째 키워드", "category": "technical", "priority": 4},
    {"keyword": "역발상 키워드", "category": "flow", "priority": 5}
  ]
}

## STEP 5 — 🆕 Python 발굴 엔진 실행 (Phase 4)

키워드 JSON 저장 후 실행:
python3 /Users/jarvis/Projects/investment-bot/data/fetch_opportunities.py

실행 후 결과 확인:
cat /Users/jarvis/Projects/investment-bot/output/intel/opportunities.json | python3 -m json.tool | head -50

## STEP 6 — 🆕 발굴 종목 종합 판단 (Phase 4)

opportunities.json 결과를 읽고:
1. composite_score 상위 3개 종목 선별
2. 각 종목에 대해:
   - 점수 분해 (수익률/RSI/감성/매크로 각 팩터)
   - AI 정성 판단 (매수 근거 + 리스크)
   - "왜 이 키워드를 골랐는지" 추론 근거
3. 발굴 ≠ 매수 추천 면책 명시

## STEP 7 — CIO 최종 보고서

전체 종합해서 ~/.openclaw/workspace/intel/cio-briefing.md 저장.

포맷:
# CIO 브리핑 — YYYY년 MM월 DD일
**수집 시각:** HH:MM KST

## EXECUTIVE SUMMARY
> 리스크 온/오프 + 한줄 요약

## 매크로 환경 (STEP 2)
## 보유 종목 액션 (STEP 3)

## 🔎 오늘의 발굴 — AI 키워드 5개 (STEP 4~6)
🏷️ #키워드1 #키워드2 #키워드3 #키워드4 #키워드5

📌 TOP 3 후보
1️⃣ 종목A (티커) — XX점
   섹터 | RSI XX | 감성 +X.X
   ├ 수익률 XX% | RSI XX% | 감성 XX% | 매크로 XX%
   └ 근거: 한줄 설명

2️⃣ 종목B ...
3️⃣ 종목C ...

💡 발굴 = 관심 후보이며, 매수 추천이 아닙니다

## 오늘 전략 한 줄

오늘 날짜, 수집 시각 포함. 임원 보고서 스타일, 한국어.
텔레그램 전송 금지 — 07:30 모닝 브리핑이 전송.
```

## 적용 방법

텔레그램에서 자비스에게:
```
크론잡 "투자팀 분석 파이프라인"의 프롬프트를 위 내용으로 업데이트해줘
```

또는 OpenClaw CLI:
```bash
openclaw cron edit 1443869e-aeb2-4dc1-b77d-5edf2b51d2a2
```
