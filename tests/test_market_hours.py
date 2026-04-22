#!/usr/bin/env python3
"""
_is_market_hours() TDD 테스트
대상: scripts/refresh_prices.py

변경 스펙:
- 기존: KRX 09:00~15:30, 미국 22:30~06:00
- 추가: 국내 장외 15:40~18:00, 미국 프리마켓 20:00~22:30
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

KST = timezone(timedelta(hours=9))


def kst(weekday: int, hour: int, minute: int = 0) -> datetime:
    """테스트용 KST datetime 생성. weekday: 0=월 ... 6=일"""
    # 2026-04-20(월) 기준 weekday 오프셋 적용
    base = datetime(2026, 4, 20, tzinfo=KST)
    return base + timedelta(days=weekday, hours=hour, minutes=minute)


def is_market(dt: datetime) -> bool:
    """refresh_prices._is_market_hours()를 datetime 인자로 호출"""
    from scripts.refresh_prices import _is_market_hours
    return _is_market_hours(dt)


class TestKrxRegular(unittest.TestCase):
    """KRX 정규장: 평일 09:00~15:30"""

    def test_krx_open(self):
        self.assertTrue(is_market(kst(0, 9, 0)))

    def test_krx_mid(self):
        self.assertTrue(is_market(kst(0, 12, 0)))

    def test_krx_close(self):
        self.assertTrue(is_market(kst(0, 15, 30)))

    def test_krx_before_open(self):
        self.assertFalse(is_market(kst(0, 8, 59)))

    def test_krx_after_close(self):
        """15:31은 정규장 아님 — 장외로 넘어가야"""
        self.assertFalse(is_market(kst(0, 15, 31)))


class TestKrxAfterHours(unittest.TestCase):
    """국내 장외: 평일 15:40~18:00 (신규 추가 구간)"""

    def test_after_hours_start(self):
        self.assertTrue(is_market(kst(0, 15, 40)))

    def test_after_hours_mid(self):
        self.assertTrue(is_market(kst(0, 17, 0)))

    def test_after_hours_end(self):
        self.assertTrue(is_market(kst(0, 18, 0)))

    def test_after_hours_gap_15_31(self):
        """15:31~15:39는 장외도 아님 (정규장↔장외 공백)"""
        self.assertFalse(is_market(kst(0, 15, 35)))

    def test_after_hours_over(self):
        """18:01은 장외 끝"""
        self.assertFalse(is_market(kst(0, 18, 1)))

    def test_after_hours_weekend(self):
        """주말 장외 없음"""
        self.assertFalse(is_market(kst(5, 16, 0)))  # 토요일


class TestUsPremarket(unittest.TestCase):
    """미국 프리마켓: 평일 20:00~22:30 KST (신규 추가 구간)"""

    def test_premarket_start(self):
        self.assertTrue(is_market(kst(0, 20, 0)))

    def test_premarket_mid(self):
        self.assertTrue(is_market(kst(0, 21, 0)))

    def test_premarket_end(self):
        self.assertTrue(is_market(kst(0, 22, 30)))

    def test_premarket_before(self):
        """19:59는 프리마켓 아님"""
        self.assertFalse(is_market(kst(0, 19, 59)))

    def test_premarket_weekend(self):
        """주말 프리마켓 없음"""
        self.assertFalse(is_market(kst(5, 21, 0)))  # 토요일


class TestUsRegular(unittest.TestCase):
    """미국 정규장: 평일 22:30~다음날 06:00 KST (기존)"""

    def test_us_open(self):
        self.assertTrue(is_market(kst(0, 22, 30)))

    def test_us_midnight(self):
        self.assertTrue(is_market(kst(1, 0, 0)))  # 화요일 자정

    def test_us_close(self):
        self.assertTrue(is_market(kst(1, 6, 0)))

    def test_us_after_close(self):
        self.assertFalse(is_market(kst(1, 6, 1)))

    def test_sunday_us_open(self):
        """일요일 22:30 미국장 시작"""
        self.assertTrue(is_market(kst(6, 22, 30)))


class TestDeadZones(unittest.TestCase):
    """수집 불필요 구간 — False여야 함"""

    def test_dead_zone_18_to_20(self):
        """18:01~19:59 — 장외 끝나고 프리마켓 전 공백"""
        self.assertFalse(is_market(kst(0, 19, 0)))

    def test_dead_zone_early_morning(self):
        """06:01~08:59 — 미국장 마감 후 KRX 개장 전"""
        self.assertFalse(is_market(kst(0, 7, 0)))

    def test_weekend_all_day(self):
        """토요일 낮"""
        self.assertFalse(is_market(kst(5, 12, 0)))


if __name__ == "__main__":
    unittest.main()
