#!/usr/bin/env python3
"""
실시간 포트폴리오 주가 조회 스크립트
Yahoo Finance API 사용 (무료, 키 불필요)
"""
import urllib.request, json, datetime

# 포트폴리오 종목 정의
# (이름, 야후티커, 평균단가, 통화, 수량)
PORTFOLIO = [
    ("삼성전자",           "005930.KS", 203102, "KRW", 42),
    ("현대차",             "005380.KS", 519000, "KRW",  9),
    ("TIGER 코리아AI전력기","0117V0.KS",  16795, "KRW", 60),
    ("TIGER 미국방산TOP10","458730.KS",  15485, "KRW", 64),
    ("테슬라",             "TSLA",      394.32, "USD",  1),
    ("알파벳",             "GOOGL",     308.27, "USD",  2),
    ("SPDR S&P Oil",      "XOP",       178.26, "USD",  1),
    ("금 현물(GC)",        "GC=F",           0, "USD",  0),
]

def fetch(ticker):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)['chart']['result'][0]['meta']

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M KST")
print(f"\n📊 실시간 포트폴리오 현황 — {now}\n")
print(f"{'종목':<22} {'현재가':>12} {'전일比':>8} {'평단比':>9}")
print("─" * 58)

for name, ticker, avg, currency, qty in PORTFOLIO:
    try:
        meta = fetch(ticker)
        price = meta['regularMarketPrice']
        prev  = meta.get('chartPreviousClose', price)
        day_chg = (price - prev) / prev * 100 if prev else 0
        pnl_str = f"{(price-avg)/avg*100:+.2f}%" if avg > 0 else "   —"
        unit = "원" if currency == "KRW" else "$"
        flag = "🔴" if day_chg < -3 else ("🟡" if day_chg < 0 else "🟢")
        print(f"{flag} {name:<20} {unit}{price:>10,.0f} {day_chg:>+7.2f}% {pnl_str:>9}")
    except Exception as e:
        print(f"❌ {name:<20} 조회 실패: {e}")

print("─" * 58)
print("출처: Yahoo Finance 실시간")
