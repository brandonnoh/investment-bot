#!/usr/bin/env python3
"""
태양광 매물 수집 cron 엔트리포인트
analysis/solar_alerts.py의 run()을 호출
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    from analysis.solar_alerts import run

    run()


if __name__ == "__main__":
    main()
