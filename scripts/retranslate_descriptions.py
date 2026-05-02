#!/usr/bin/env python3
"""company_profiles 영문 description 한국어 재번역."""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import get_db_conn  # noqa: E402
from web.claude_caller import call_claude  # noqa: E402


def _is_english(text: str) -> bool:
    if not text:
        return False
    kr_chars = sum(1 for c in text if '가' <= c <= '힣')
    return kr_chars / len(text) < 0.05


def _translate(text: str) -> str:
    try:
        result = call_claude(
            f"다음 영문 기업 설명을 자연스러운 한국어로 번역해줘. 번역문만 출력해:\n\n{text[:1500]}",
            system="기업 설명 번역 전문가. 번역문만 출력하고 다른 말은 하지 마.",
        )
        return result.strip() if result else text
    except Exception as e:
        print(f"  [warn] 번역 실패: {e}")
        return text


def run() -> None:
    with get_db_conn() as conn:
        rows = conn.execute(
            "SELECT ticker, name FROM company_profiles WHERE description IS NOT NULL AND description != ''"
        ).fetchall()
        all_descs = {
            r["ticker"]: conn.execute(
                "SELECT description FROM company_profiles WHERE ticker = ?", (r["ticker"],)
            ).fetchone()["description"]
            for r in rows
        }

    targets = [
        (ticker, desc)
        for ticker, desc in all_descs.items()
        if _is_english(desc)
    ]

    print(f"[retranslate] 번역 대상: {len(targets)}개")

    with get_db_conn() as conn:
        for i, (ticker, desc) in enumerate(targets, 1):
            name_row = next((r for r in rows if r["ticker"] == ticker), None)
            name = name_row["name"] if name_row else ticker
            print(f"  ({i}/{len(targets)}) {ticker} | {name[:30]}")
            translated = _translate(desc)
            conn.execute(
                "UPDATE company_profiles SET description = ? WHERE ticker = ?",
                (translated, ticker),
            )
            conn.commit()
            time.sleep(0.5)

    print(f"[retranslate] 완료: {len(targets)}개 번역")


if __name__ == "__main__":
    run()
