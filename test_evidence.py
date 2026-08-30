"""
근거 게이트 대조군.

★ 이 스위트가 반드시 보여야 하는 것 두 방향:
   ⓐ 얇은 데이터에서 «불충분» 이 뜬다      (게이트가 실제로 막는다)
   ⓑ 두꺼운 데이터에서 «충분» 이 뜬다      (게이트가 항상 막기만 하는 게 아니다)
   ### 둘 다 없으면 «실패할 수 없는 대조군» 이다 — 통과가 아무것도 증명하지 않는다.
"""
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])

from evidence import (  # noqa: E402
    MIN_MARKETS,
    MIN_RECORDS_PER_MARKET,
    build_evidence,
    render,
)


def rec(market, price, unit_qty, qty=1, variety="일반"):
    return {
        "whsl_mrkt_nm": market,
        "scsbd_prc": price,
        "unit_qty": unit_qty,
        "qty": qty,
        "gds_sclsf_nm": variety,
    }


RESULTS = []


def check(name, cond, note=""):
    RESULTS.append((name, bool(cond), note))


# ── ⓐ 막는 쪽 ────────────────────────────────────────────────
def t_empty():
    ev = build_evidence([], "배추", "2026-08-30")
    check("EG1 기록 0건 → 불충분", not ev.sufficient)
    check("EG2 이유에 '0건' 명시", any("0건" in r for r in ev.why_insufficient()))
    check("EG3 render 에 '근거 부족'", "근거 부족" in render(ev))


def t_one_market():
    # 한 시장 5건 = 실제 조회에서 나온 모양(얇은 표본)
    items = [rec("진주", 6000, 10.0) for _ in range(5)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG4 1개 시장뿐 → 불충분", not ev.sufficient, f"시장 {len(ev.usable_markets)}")
    check("EG5 이유가 구체적(시장 수 언급)", any("시장" in r for r in ev.why_insufficient()))


def t_thin_second_market():
    # 2개 시장이나 한 곳이 임계 미만
    items = [rec("진주", 6000, 10.0) for _ in range(5)]
    items += [rec("광주각화", 9000, 10.0) for _ in range(MIN_RECORDS_PER_MARKET - 1)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG6 얇은 2번째 시장 → 불충분", not ev.sufficient)
    check("EG7 모자란 시장 이름을 댄다", any("광주각화" in r for r in ev.why_insufficient()))


# ── ⓑ 통과하는 쪽 (이게 없으면 게이트가 헛돈다) ──────────────
def t_sufficient():
    items = [rec("진주", 6000, 10.0) for _ in range(5)]
    items += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG8 두꺼운 데이터 → 충분", ev.sufficient, f"시장 {len(ev.usable_markets)} 건수 {ev.n_total}")
    r = render(ev)
    check("EG9 render 에 '비교 가능'", "비교 가능" in r)
    check("EG10 근거 건수를 답과 함께 낸다", "근거 5건" in r)


# ── 단위 환산 ────────────────────────────────────────────────
def t_unit_normalization():
    """★ 규격이 섞이면 원단가 평균은 뒤집힌다. 원/kg 로 맞추면 안 뒤집힌다."""
    # A: 10kg 에 20,000원 = 2,000원/kg   B: 5kg 에 15,000원 = 3,000원/kg
    # 원단가만 보면 A(20,000) > B(15,000) 라 A 가 비싸 보인다. 실제로는 B 가 비싸다.
    items = [rec("A시장", 20000, 10.0) for _ in range(5)]
    items += [rec("B시장", 15000, 5.0) for _ in range(5)]
    ev = build_evidence(items, "사과", "2026-08-28")
    top = ev.usable_markets[0]
    check("EG11 원/kg 로 순위가 바로잡힌다", top.market == "B시장", f"1위={top.market}")
    check("EG12 A 는 2,000원/kg", abs(ev.usable_markets[-1].won_per_kg_avg - 2000) < 1)


def t_mixed_pack_flagged():
    items = [rec("가락", 20000, 10.0) for _ in range(3)]
    items += [rec("가락", 30000, 15.0) for _ in range(3)]
    items += [rec("진주", 6000, 10.0) for _ in range(5)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG13 섞인 규격을 표시한다", any("규격이 섞여" in c for c in ev.caveats()))


def t_unconvertible_counted_not_dropped():
    """단위중량 0 인 건을 «조용히 버리지» 않는다. 세어서 알린다."""
    items = [rec("진주", 6000, 10.0) for _ in range(5)]
    items += [rec("진주", 6000, 0) for _ in range(2)]  # 환산 불가
    items += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG14 환산 불가 2건을 센다", ev.n_dropped_total == 2, f"={ev.n_dropped_total}")
    check("EG15 caveat 에 알린다", any("환산" in c for c in ev.caveats()))
    check("EG16 평균에 안 섞인다", abs(ev.usable_markets[-1].won_per_kg_avg - 600) < 1)


def t_zero_price_ignored():
    items = [rec("진주", 0, 10.0) for _ in range(9)]
    items += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(items, "배추", "2026-08-28")
    check("EG17 단가 0 은 시장으로 안 센다", len(ev.usable_markets) == 1)
    check("EG18 그래서 불충분", not ev.sufficient)


# ── 덮음률 (아래 회귀 시험이 이 축을 만들었다) ────────────────────────────────
def t_truncated_blocks_even_with_many_records():
    """### 회귀 시험 — 우리가 실제로 낸 오류다. 이게 없으면 또 낸다.

    건수도 충분하고 시장도 2곳인데 «하루의 0.77% 만 본 표본» 이면 비교를 막아야 한다.
    못 본 시장이 더 비쌀 수 있고 우리는 그것을 배제하지 못한다.
    """
    items = [rec("진주", 6000, 10.0) for _ in range(50)]
    items += [rec("광주각화", 9000, 10.0) for _ in range(50)]
    ev = build_evidence(
        items, "배추", "2026-08-28", day_total=129_536, all_day_items=[rec("진주", 1, 1)] * 1000
    )
    check("EG19 절단 표본이면 건수가 많아도 불충분", not ev.sufficient, f"건수 {ev.n_total}")
    check("EG20 이유에 덮음률(%)을 댄다", any("%" in r for r in ev.why_insufficient()))
    check(
        "EG21 '못 본' 과 '없는' 을 구별해 말한다",
        any("못 본" in r for r in ev.why_insufficient()),
    )


def t_full_day_passes():
    """전량이면 통과해야 한다 — 안 그러면 게이트가 항상 막기만 한다."""
    day = [rec("진주", 6000, 10.0) for _ in range(5)]
    day += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(day, "배추", "2026-08-28", day_total=len(day), all_day_items=day)
    check("EG22 전량 표본 → 충분", ev.sufficient)
    check("EG23 절단 경고 없음", not any("만 봤다" in c for c in ev.caveats()))


def t_unknown_total_is_flagged():
    """전체 건수를 «모르는» 것과 «다 본» 것은 다르다."""
    day = [rec("진주", 6000, 10.0) for _ in range(5)]
    day += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(day, "배추", "2026-08-28", day_total=None, all_day_items=day)
    check("EG24 총계 미상은 caveat 로 알린다", any("판정 불가" in c for c in ev.caveats()))
    check("EG25 그래도 막지는 않는다(모름 ≠ 절단)", ev.sufficient)


def t_market_coverage_reported():
    day = [rec("진주", 6000, 10.0) for _ in range(5)]
    day += [rec("가락", 9000, 10.0) for _ in range(5)]
    ev = build_evidence(day, "배추", "2026-08-28", day_total=len(day), all_day_items=day)
    check("EG26 표본 시장 수를 알린다", any("33곳" in c or "/33" in c for c in ev.caveats()))


def main() -> int:
    for f in (
        t_empty,
        t_one_market,
        t_thin_second_market,
        t_sufficient,
        t_unit_normalization,
        t_mixed_pack_flagged,
        t_unconvertible_counted_not_dropped,
        t_zero_price_ignored,
        t_truncated_blocks_even_with_many_records,
        t_full_day_passes,
        t_unknown_total_is_flagged,
        t_market_coverage_reported,
    ):
        f()

    print("=" * 64)
    for name, ok, note in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{note}]" if note else ""))
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 64)
    print(f"{n_ok}/{len(RESULTS)} PASS")

    blocks = [n for n, ok, _ in RESULTS if ok and n.startswith(("EG1 ", "EG4", "EG6"))]
    passes = [n for n, ok, _ in RESULTS if ok and n.startswith("EG8")]
    print(f"반증자 확인: 막는 사례 {len(blocks)}건 · 통과 사례 {len(passes)}건")
    if not blocks or not passes:
        print("  🔴 한 방향만 있다 = 실패할 수 없는 대조군이다. 통과를 근거로 쓰지 마라.")
        return 1
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
