# HEARTBEAT.md — OpenClaw 크론잡 & 알림 핸들러 안내

> 최종 업데이트: 2026-03-23

---

## 현재 등록된 크론잡

| 시간 (KST) | 이름 | 역할 | 세션 |
|-------------|------|------|------|
| 05:30 | 투자팀 분석 파이프라인 | 전략/CIO 보고서 생성 | isolated |
| 07:30 | 모닝 브리핑 | 종합 브리핑 텔레그램 전송 | isolated |
| 16:00 (평일) | 장 마감 리포트 | 오늘 결산 + 내일 전략 텔레그램 전송 | isolated |

```bash
# 크론잡 확인
openclaw cron list
```

---

## 긴급 알림 (system event) 핸들러

`alerts_watch.py`가 임계값 초과 감지 시 자동 실행:
```
openclaw system event --text "🚨 투자 알림: [내용]" --mode now
```

### 자비스 동작 순서
1. system event 수신 → 즉시 wake
2. `output/intel/alerts.json` 읽기
3. `python3 data/realtime.py` 실행 (현재 수치 재확인)
4. Brave 검색 (관련 뉴스)
5. 텔레그램 즉시 전송

### 알림 텔레그램 형식
```
🚨 긴급 알림 — [시간] KST

🔴 삼성전자 -5.72% 급락
현재가: 188,000원 | 평단比: -7.44%

📰 관련 뉴스: "..."

💡 판단: [AI 분석 코멘트]
```

### 중복 방지
- 같은 종목 + 같은 방향 알림은 **1시간 내 재발송 금지**
- DB `alerts` 테이블의 `notified` 컬럼으로 추적
- 알림 없으면 system event **절대 실행 안 함** (토큰 낭비 방지)

---

## crontab (맥미니)

```bash
# 확인
crontab -l

# 재설치 (필요 시)
crontab /tmp/investment-bot-crontab
```

### 스케줄
| 시간 | 프로그램 | 역할 |
|------|---------|------|
| 매 10분 (09~15시 평일) | fetch_prices.py | 주가 수집 |
| 매 10분 (09~15시 평일) | fetch_macro.py | 매크로 수집 |
| 매 10분 (09~15시 평일) | alerts_watch.py | 알림 감시 + system event |
| 15:40 (평일) | closing.py | 장 마감 리포트 생성 |
| 매 1시간 | fetch_news.py | 뉴스 수집 |
| 05:00 | run_pipeline.py | 일일 전체 파이프라인 |
| 월 04:00 | run_pipeline.py --weekly | 주간 리포트 |

---

## 임계값 (config.py)

| 이벤트 | 임계값 | 레벨 |
|--------|--------|------|
| 종목 급락 | -5% | RED |
| 종목 급등 | +5% | GREEN |
| 코스피 폭락 | -3% | RED |
| 환율 급등 | 1,550원 | RED |
| 유가 급등 | +5% | YELLOW |
| 금 현물 급변 | ±3% | YELLOW |
| VIX 급등 | 30 | YELLOW |
| 포트폴리오 손실 | -10% | RED |
