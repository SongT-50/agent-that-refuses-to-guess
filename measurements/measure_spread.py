"""
실측 — **"시장 간 가격 차이 80%" 를 대외 문구에 쓰기 전에**

초안에 *"prices for the same crop on the same day can differ by 80% between markets"* 라고 썼다.
### 그 80% 는 «복숭아 · 8/28 · 원주↔부산반여» 하나에서 나왔다. 그것을 일반 문장으로 썼다.
   = 우리가 오늘 계속 잡은 그 형태(한 점을 특성으로).

⇒ 쓰기 전에 잰다. 전량 캐시 전체에서 «1위 ↔ 최하위» 격차 분포를 낸다.
비용 0 (캐시). LLM 안 씀.
"""
from __future__ import annotations

import os
import statistics
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import cached_dates, filter_product, load_day  # noqa: E402
from evidence import build_evidence  # noqa: E402

PRODUCTS = ["배추", "사과", "감자", "양파", "토마토", "포도", "복숭아", "오이"]


def main() -> int:
    dates = cached_dates()
    if not dates:
        print("전량 캐시 없음")
        return 1

    rows = []
    for date in dates:
        day = load_day(date)
        for kw in PRODUCTS:
            sub = filter_product(day.items, kw)
            if not sub:
                continue
            ev = build_evidence(
                sub, kw, date, day_total=day.day_total, all_day_items=day.items
            )
            if not ev.sufficient:
                continue
            u = ev.usable_markets
            top, bot = u[0], u[-1]
            if bot.won_per_kg_avg <= 0:
                continue
            pct = (top.won_per_kg_avg - bot.won_per_kg_avg) / bot.won_per_kg_avg * 100
            rows.append((date, kw, len(u), top.market, bot.market, pct))

    rows.sort(key=lambda r: r[5])
    print("=" * 76)
    print("시장 간 격차 (1위 ↔ 최하위, 원/kg 중앙값 기준)")
    print("=" * 76)
    for d, kw, n, t, b, p in rows:
        print(f"  {d} {kw:5s} | {n:2d}개 시장 | {t:6s} ↔ {b:6s} | {p:6.0f}%")

    pcts = [r[5] for r in rows]
    print("\n" + "=" * 76)
    print(
        f"  n={len(pcts)}  최소 {min(pcts):.0f}%  중앙 {statistics.median(pcts):.0f}%  최대 {max(pcts):.0f}%"
    )
    print("=" * 76)
    print("\n대외 문구로 쓸 수 있는 표현:")
    print(f'  ❌ "80% 차이가 난다"          — 한 점이다')
    print(
        f'  ✅ "같은 날 같은 품목인데 시장 간 격차가 {min(pcts):.0f}~{max(pcts):.0f}% 다'
        f' (중앙 {statistics.median(pcts):.0f}%, n={len(pcts)})"'
    )
    print(f"\n  ⚠️ 표본 = 전량 캐시 {len(dates)}일 × 품목 {len(PRODUCTS)}종. 이 밖은 안 쟀다.")
    print("  ⚠️ 격차는 «중앙값끼리» 의 차이다. 개별 거래의 최고·최저 차이는 훨씬 크다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
