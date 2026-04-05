#!/usr/bin/env python3
"""
뉴스 감성 분석 키워드 상수 모듈 — 한/영 금융 도메인 키워드 사전
- 한국어 긍정/부정 키워드
- 영어 긍정/부정 키워드
외부 패키지 없이 순수 stdlib만 사용
"""

# ── 한국어 긍정 키워드 (금융 도메인) ──
KO_POSITIVE = frozenset(
    [
        "급등",
        "상승",
        "호조",
        "호재",
        "매출 증가",
        "영업이익",
        "사상 최대",
        "신고가",
        "돌파",
        "반등",
        "회복",
        "강세",
        "매수",
        "순매수",
        "성장",
        "확대",
        "투자 확대",
        "수출 증가",
        "흑자",
        "개선",
        "기대",
        "전망 밝",
        "수혜",
        "최고치",
        "상향",
        "호황",
        "안정",
        "완화",
        "유입",
        "상승세",
        "이익 증가",
    ]
)

# ── 한국어 부정 키워드 (금융 도메인) ──
KO_NEGATIVE = frozenset(
    [
        "급락",
        "폭락",
        "하락",
        "악재",
        "매출 감소",
        "적자",
        "손실",
        "침체",
        "위기",
        "불안",
        "매도",
        "순매도",
        "투매",
        "하향",
        "축소",
        "감소",
        "둔화",
        "약세",
        "저조",
        "우려",
        "리스크",
        "불확실",
        "전쟁",
        "제재",
        "파산",
        "폭탄",
        "디폴트",
        "인플레이션",
        "긴축",
        "유출",
        "하락세",
    ]
)

# ── 영어 긍정 키워드 (금융 도메인) ──
EN_POSITIVE = frozenset(
    [
        "surge",
        "rally",
        "gain",
        "bullish",
        "beat",
        "growth",
        "profit",
        "revenue",
        "upgrade",
        "outperform",
        "record high",
        "recovery",
        "strong",
        "boost",
        "optimistic",
        "upside",
        "buy",
        "accumulate",
        "breakout",
        "expansion",
        "earnings beat",
        "positive",
        "improve",
        "advance",
        "momentum",
        "all-time high",
    ]
)

# ── 영어 부정 키워드 (금융 도메인) ──
EN_NEGATIVE = frozenset(
    [
        "crash",
        "plunge",
        "drop",
        "bearish",
        "miss",
        "decline",
        "loss",
        "deficit",
        "downgrade",
        "underperform",
        "sell-off",
        "recession",
        "weak",
        "risk",
        "pessimistic",
        "downside",
        "sell",
        "bankruptcy",
        "default",
        "inflation",
        "fear",
        "negative",
        "worsen",
        "slump",
        "crisis",
        "warning",
    ]
)
