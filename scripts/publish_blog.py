"""
cio-briefing.md, marcus-analysis.md → 영어 변환 → Sanity 발행
파이프라인 완료 후 07:55에 실행
"""
import os
import re
import requests
from pathlib import Path
from datetime import datetime, timezone

INTEL_DIR = Path("/app/output/intel")
SANITY_PROJECT_ID = os.environ["SANITY_PROJECT_ID"]
SANITY_DATASET = os.environ.get("SANITY_DATASET", "production")
SANITY_TOKEN = os.environ["SANITY_API_WRITE_TOKEN"]
GEMINI_API_KEY = os.environ["GOOGLE_GEMINI_API_KEY"]

SANITY_API = (
    f"https://{SANITY_PROJECT_ID}.api.sanity.io"
    f"/v2026-04-29/data/mutate/{SANITY_DATASET}"
)

POSTS_TO_PUBLISH = [
    {
        "source": "cio-briefing.md",
        "category": "market-analysis",
        "title_prefix": "Daily Market Brief",
    },
    {
        "source": "marcus-analysis.md",
        "category": "stock-picks",
        "title_prefix": "Today's Top Stock Picks",
    },
]


def translate_to_english(korean_text: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        "Translate this Korean financial analysis to professional English.\n"
        "Keep all numbers, tickers, and percentages exactly as-is.\n"
        "Remove personal portfolio details (specific buy prices, personal holdings).\n"
        "Frame as market data analysis, not investment advice.\n"
        'Add disclaimer: "This is data analysis, not investment advice."\n\n'
        f"Korean text:\n{korean_text[:3000]}"
    )
    resp = requests.post(
        url,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def slugify(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return clean[:100]


def publish_to_sanity(title: str, slug: str, body: str, category: str):
    doc = {
        "_type": "post",
        "_id": f"auto-{slug}",
        "title": title,
        "slug": {"_type": "slug", "current": slug},
        "publishedAt": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "categories": [category],
        "body": [{"_type": "block", "children": [{"_type": "span", "text": body}]}],
        "excerpt": body[:160],
    }
    resp = requests.post(
        SANITY_API,
        headers={
            "Authorization": f"Bearer {SANITY_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"mutations": [{"createOrReplace": doc}]},
        timeout=15,
    )
    resp.raise_for_status()
    print(f"[OK] Published: {title}")


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for config in POSTS_TO_PUBLISH:
        path = INTEL_DIR / config["source"]
        if not path.exists():
            print(f"[SKIP] {config['source']} not found")
            continue
        korean_text = path.read_text(encoding="utf-8")
        english_text = translate_to_english(korean_text)
        title = f"{config['title_prefix']} — {today}"
        slug = slugify(f"{config['title_prefix']}-{today}")
        publish_to_sanity(title, slug, english_text, config["category"])


if __name__ == "__main__":
    main()
