"""
실측 — **두 고침을 «따로» 잰다**

앞선 측정(43.8%)은 «원단가 평균» ↔ «원/kg 평균» 을 비교했다.
그 뒤 나는 대표값을 **중앙값**으로 바꿨다(이상치 한 건이 광주각화 평균을 21% 끌었다).
### ⇒ 이제 코드가 두 군데 달라졌고, 43.8% 는 «지금 코드» 를 설명하지 않는다.

한꺼번에 재면 두 효과가 섞인다. 그래서 셋을 나란히 놓고 «어느 고침이 무엇을 바꿨나» 를 가른다:
  ⓐ 원단가 평균   = 기존 도구 방식
  ⓑ 원/kg 평균    = 단위만 맞춤
  ⓒ 원/kg 중앙값  = 단위 + 이상치 (지금 우리 코드)

비용 0 (캐시). LLM 안 씀.
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import cached_dates, filter_product, load_day  # noqa: E402
from evidence import MIN_RECORDS_PER_MARKET  # noqa: E402

PRODUCTS = ["배추", "사과", "감자", "양파", "토마토", "포도", "복숭아", "오이"]


def per_market(items: list[dict]):
    """시장별 (원단가 목록, 원/kg 목록)."""
    raw = defaultdict(list)
    pk = defaultdict(list)
    for it in items:
        m = (it.get("whsl_mrkt_nm") or "").strip()
        try:
            p = float(it.get("scsbd_prc", 0))
            u = float(it.get("unit_qty", 0))
        except (TypeError, ValueError):
            continue
        if not m or p <= 0:
            continue
        raw[m].append(p)
        if u > 0:
            pk[m].append(p / u)
    return raw, pk


def top_of(d: dict, fn) -> str | None:
    cand = {m: fn(v) for m, v in d.items() if len(v) >= MIN_RECORDS_PER_MARKET}
    if len(cand) < 2:
        return None
    return max(cand, key=cand.get)


def main() -> int:
    dates = cached_dates()
    if not dates:
        print("전량 캐시가 없다 — measure_unit_effect.py 를 먼저 돌려라")
        return 1

    n = 0
    flip_unit = 0  # ⓐ→ⓑ  단위 맞추기가 1위를 바꿨나
    flip_outlier = 0  # ⓑ→ⓒ  이상치 처리(중앙값)가 1위를 바꿨나
    flip_total = 0  # ⓐ→ⓒ  둘 합쳐서
    detail = []

    for date in dates:
        day = load_day(date)
        for kw in PRODUCTS:
            sub = filter_product(day.items, kw)
            if not sub:
                continue
            raw, pk = per_market(sub)
            a = top_of(raw, statistics.mean)
            b = top_of(pk, statistics.mean)
            c = top_of(pk, statistics.median)
            if not (a and b and c):
                continue
            n += 1
            if a != b:
                flip_unit += 1
            if b != c:
                flip_outlier += 1
            if a != c:
                flip_total += 1
            if a != c:
                detail.append((date, kw, a, b, c))

    print("=" * 74)
    print("두 고침을 따로 재기 — 1위 시장이 바뀌나")
    print("=" * 74)
    print(f"  대상 (날짜×품목) 쌍 : {n}   (전량 캐시 {len(dates)}일)")
    print()
    print(f"  ⓐ→ⓑ 단위 맞추기가 바꾼 쌍   : {flip_unit}")
    print(f"  ⓑ→ⓒ 이상치 처리가 바꾼 쌍   : {flip_outlier}")
    print(f"  ⓐ→ⓒ 둘 합쳐 바뀐 쌍         : {flip_total}")
    if detail:
        print("\n  바뀐 사례 (원단가평균 → 원/kg평균 → 원/kg중앙):")
        for d, kw, a, b, c in detail:
            mark = "  [이상치도 작용]" if b != c else ""
            print(f"    {d} {kw:5s} : {a} → {b} → {c}{mark}")
    print()
    print(f"  ⚠️ n={n}. 비율로 인용하지 마라. 「어느 고침이 작용했나」를 가르는 것이 목적이다.")
    print(f"  ⚠️ 품목 {len(PRODUCTS)}종은 내가 골랐고 날짜는 {len(dates)}일이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
