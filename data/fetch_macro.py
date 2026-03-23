#!/usr/bin/env python3
"""
매크로 지표 수집 + SQLite 저장
코스피, 코스닥, 원/달러, WTI, 브렌트유, 금, DXY, VIX
출력: output/intel/macro.json
"""
import json
import sqlite3
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MACRO_INDICATORS, DB_PATH, OUTPUT_DIR, YAHOO_HEADERS, YAHOO_TIMEOUT
from db.init_db import init_db

KST = timezone(timedelta(hours=9))


def fetch_yahoo_quote(ticker: str) -> dict:
    """Yahoo Finance에서 지표 시세 조회"""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=YAHOO_TIMEOUT) as resp:
            data = json.load(resp)
            result = data["chart"]["result"]
            if not result:
                raise ValueError(f"데이터 없음: {ticker}")
            return result[0]["meta"]
    except urllib.error.URLError as e:
        raise ConnectionError(f"네트워크 오류 ({ticker}): {e}")
    except (KeyError, IndexError) as e:
        raise ValueError(f"응답 파싱 실패 ({ticker}): {e}")


def collect_macro() -> list[dict]:
    """매크로 지표 전체 수집"""
    now = datetime.now(KST).isoformat()
    results = []

    for indicator in MACRO_INDICATORS:
        ticker = indicator["ticker"]
        name = indicator["name"]
        try:
            meta = fetch_yahoo_quote(ticker)
            value = meta["regularMarketPrice"]
            prev_close = meta.get("chartPreviousClose", meta.get("previousClose", value))

            # 전일 대비 변동률
            change_pct = round((value - prev_close) / prev_close * 100, 2) if prev_close else 0.0

            record = {
                "indicator": name,
                "ticker": ticker,
                "value": value,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "category": indicator["category"],
                "timestamp": now,
            }
            results.append(record)

            # 환율은 값 자체가 중요하므로 별도 표시
            if ticker == "KRW=X":
                print(f"  ✅ {name}: {value:,.2f}원 ({change_pct:+.2f}%)")
            else:
                print(f"  ✅ {name}: {value:,.2f} ({change_pct:+.2f}%)")

        except Exception as e:
            print(f"  ❌ {name} ({ticker}): {e}")
            results.append({
                "indicator": name,
                "ticker": ticker,
                "value": None,
                "prev_close": None,
                "change_pct": None,
                "category": indicator["category"],
                "timestamp": now,
                "error": str(e),
            })

    return results


def save_to_db(records: list[dict]):
    """매크로 지표를 SQLite에 저장"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        inserted = 0

        for r in records:
            if r.get("value") is None:
                continue
            cursor.execute(
                """INSERT INTO macro (indicator, value, change_pct, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (r["indicator"], r["value"], r["change_pct"], r["timestamp"]),
            )
            inserted += 1

        conn.commit()
        print(f"  💾 DB 저장 완료: {inserted}건")
    finally:
        conn.close()


def save_to_json(records: list[dict]):
    """매크로 지표를 JSON 파일로 출력"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "macro.json"

    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "count": len([r for r in records if r.get("value") is not None]),
        "indicators": records,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON 저장: {output_path}")


def run():
    """매크로 지표 수집 파이프라인 실행"""
    print(f"\n🌍 매크로 지표 수집 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # DB 초기화 확인
    if not DB_PATH.exists():
        init_db()

    # 지표 수집
    records = collect_macro()

    # 저장
    save_to_db(records)
    save_to_json(records)

    success = len([r for r in records if r.get("value") is not None])
    fail = len(records) - success
    print(f"\n✅ 매크로 수집 완료: 성공 {success}건, 실패 {fail}건\n")

    return records


if __name__ == "__main__":
    run()
