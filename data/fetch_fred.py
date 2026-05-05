#!/usr/bin/env python3
"""
FRED API 경제 지표 수집 + SQLite 저장
미국 기준금리, 10년물 국채, 장단기 금리차, CPI, 실업률, GDP, VIX, 달러 인덱스
출력: output/intel/fred_macro.json
"""

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 모듈 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, FRED_API_KEY, FRED_SERIES, OUTPUT_DIR
from db.init_db import init_db

KST = timezone(timedelta(hours=9))
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_series(series_id: str) -> list[dict]:
    """FRED API에서 특정 시리즈의 최근 관측값 2개를 가져온다."""
    params = (
        f"?series_id={series_id}"
        f"&api_key={FRED_API_KEY}"
        f"&limit=2"
        f"&sort_order=desc"
        f"&file_type=json"
    )
    url = FRED_BASE_URL + params
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "investment-bot/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("observations", [])
    except (urllib.error.URLError, OSError) as e:
        print(f"  ❌ FRED {series_id} 요청 실패: {e}")
        return []


def _parse_value(raw: str) -> float | None:
    """FRED 관측값 파싱. '.'(결측치)이면 None 반환."""
    if raw == ".":
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _calc_change_pct(current: float, prev: float | None) -> float:
    """변화율 계산. 직전값이 없거나 0이면 0.0 반환."""
    if prev is None or prev == 0:
        return 0.0
    return round((current - prev) / abs(prev) * 100, 2)


def collect_fred() -> list[dict]:
    """FRED 시리즈 전체 수집. API 키 없으면 빈 리스트 반환."""
    if not FRED_API_KEY:
        print("  ⚠️ FRED_API_KEY 미설정 — FRED 수집 건너뜀")
        return []

    now = datetime.now(KST).isoformat()
    results = []

    for series_id, meta in FRED_SERIES.items():
        try:
            obs = _fetch_series(series_id)
            if not obs:
                print(f"  ❌ {meta['name']} ({series_id}): 데이터 없음")
                results.append(_error_record(series_id, meta, now, "데이터 없음"))
                continue

            current_val = _parse_value(obs[0].get("value", "."))
            if current_val is None:
                print(f"  ❌ {meta['name']} ({series_id}): 값 파싱 실패")
                results.append(_error_record(series_id, meta, now, "값 파싱 실패"))
                continue

            prev_val = _parse_value(obs[1].get("value", ".")) if len(obs) > 1 else None
            change_pct = _calc_change_pct(current_val, prev_val)

            record = {
                "indicator": series_id,
                "name": meta["name"],
                "value": current_val,
                "prev_value": prev_val,
                "change_pct": change_pct,
                "unit": meta["unit"],
                "category": meta["category"],
                "timestamp": now,
                "source": "FRED",
            }
            results.append(record)
            print(f"  ✅ {meta['name']}: {current_val} {meta['unit']} ({change_pct:+.2f}%)")

        except Exception as e:
            print(f"  ❌ {meta['name']} ({series_id}): {e}")
            results.append(_error_record(series_id, meta, now, str(e)))

    return results


def _error_record(series_id: str, meta: dict, ts: str, error: str) -> dict:
    """에러 발생 시 빈 레코드 생성."""
    return {
        "indicator": series_id,
        "name": meta["name"],
        "value": None,
        "prev_value": None,
        "change_pct": None,
        "unit": meta["unit"],
        "category": meta["category"],
        "timestamp": ts,
        "source": "FRED",
        "error": error,
    }


def save_to_db(records: list[dict]):
    """FRED 지표를 macro 테이블에 저장 (source='FRED')."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        inserted = 0
        for r in records:
            if r.get("value") is None:
                continue
            cursor.execute(
                "INSERT INTO macro (indicator, value, change_pct, timestamp) VALUES (?, ?, ?, ?)",
                (r["indicator"], r["value"], r["change_pct"], r["timestamp"]),
            )
            inserted += 1
        conn.commit()
        print(f"  💾 FRED DB 저장: {inserted}건")
    finally:
        conn.close()


def save_to_json(records: list[dict]):
    """FRED 지표를 JSON 파일로 저장."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "fred_macro.json"
    output = {
        "updated_at": datetime.now(KST).isoformat(),
        "source": "FRED",
        "indicators": records,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON 저장: {output_path}")


def run():
    """FRED 경제 지표 수집 파이프라인 실행."""
    print(f"\n📊 FRED 경제 지표 수집 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    if not DB_PATH.exists():
        init_db()

    records = collect_fred()
    if not records:
        print("  ℹ️ 수집 결과 없음 — 저장 건너뜀")
        return records

    save_to_db(records)
    save_to_json(records)

    success = len([r for r in records if r.get("value") is not None])
    fail = len(records) - success
    print(f"\n✅ FRED 수집 완료: 성공 {success}건, 실패 {fail}건\n")
    return records


if __name__ == "__main__":
    run()
