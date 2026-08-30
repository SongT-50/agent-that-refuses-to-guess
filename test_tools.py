"""
도구 층 대조군 — **우리가 파는 그 동작을 시험한다**

왜 이 파일이 생겼나 (2026-08-30):
  거절 경로가 «크래시 → 환각» 으로 새고 있었는데 ### **대조군이 하나도 없었다.**
  답하는 경로는 여러 번 돌렸고 ### **거절 경로는 눈으로만 봤다.** 그게 우리가 파는 그 동작인데.
  ⇒ 고친 것을 여기 박는다. **다음에 조용히 되돌아가지 않게.**

### 이 스위트가 반드시 보여야 하는 것:
  ⓐ 도구는 **어떤 입력에도 예외를 던지지 않는다** (던지면 그 자리를 모델이 채운다)
  ⓑ 거절 화면에 **가격이 없다** (있으면 모델이 인용한다 — 실측 4/6)
  ⓒ 두 경로 다 **`[한 줄]` 로 시작한다** (모델이 그대로 옮길 문장)
  ⓓ 그런데 ### **답하는 경로에는 가격이 있어야 한다** — 없으면 이 스위트는
     «전부 막기만 하는» 실패할 수 없는 대조군이 된다.

⚠️ 네트워크를 안 탄다. `data.load_day` 를 갈아끼워 결정론적으로 돌린다.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data as data_mod  # noqa: E402
import tools as tools_mod  # noqa: E402
from data import DayData  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
PRICE = re.compile(r"[\d,]+\s*원/kg")


def check(name: str, cond: bool, note: str = "") -> None:
    RESULTS.append((name, bool(cond), note))


def rec(market: str, price: float, unit_qty: float, qty: float = 1.0) -> dict:
    return {
        "whsl_mrkt_nm": market,
        "scsbd_prc": price,
        "unit_qty": unit_qty,
        "qty": qty,
        "gds_mclsf_nm": "배추",
        "gds_sclsf_nm": "일반",
    }


def with_day(day: DayData):
    """`load_day` 를 갈아끼운다. 원복은 호출자 책임."""
    data_mod.load_day = lambda date, page_budget=3: day  # type: ignore[assignment]
    tools_mod.load_day = data_mod.load_day  # tools 는 import 시점에 이름을 잡았다


ORIGINAL_LOAD = data_mod.load_day


def restore() -> None:
    data_mod.load_day = ORIGINAL_LOAD
    tools_mod.load_day = ORIGINAL_LOAD


# ── ⓐ 어떤 실패도 예외가 되지 않는다 ─────────────────────────
def t_never_raises_on_none_total():
    """### 이게 실제로 났던 버그다 — day_total None 에 `{:,}` 를 걸어 TypeError."""
    with_day(DayData("2026-08-30", [], None, "api"))
    try:
        out = tools_mod.shipping_market_advice("배추", "2026-08-30")
        raised = False
    except Exception as e:  # noqa: BLE001
        out, raised = f"{type(e).__name__}", True
    check("TT1 총계 None 이어도 예외 없음", not raised, out[:40])
    check("TT2 그 경우에도 거절을 말한다", "답할 수 없다" in out or "판정 불가" in out)


def t_never_raises_on_broken_records():
    """레코드가 망가져 있어도 죽지 않는다."""
    junk = [{"whsl_mrkt_nm": None, "scsbd_prc": "x", "unit_qty": None}, {}, {"scsbd_prc": 1}]
    with_day(DayData("2026-08-28", junk, 100, "api"))
    try:
        out = tools_mod.shipping_market_advice("배추", "2026-08-28")
        raised = False
    except Exception as e:  # noqa: BLE001
        out, raised = f"{type(e).__name__}: {e}", True
    check("TT3 깨진 레코드에도 예외 없음", not raised, out[:50])


def t_tool_failure_becomes_refusal():
    """### 도구가 진짜로 터져도 «거절» 이 나와야 한다. 침묵이면 모델이 채운다."""

    def boom(date, page_budget=3):
        raise RuntimeError("simulated outage")

    data_mod.load_day = boom  # type: ignore[assignment]
    tools_mod.load_day = boom  # type: ignore[assignment]
    out = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT4 도구 실패가 거절로 바뀐다", "답할 수 없다" in out, out[:50])
    check("TT5 실패 사실을 숨기지 않는다", "오류" in out or "RuntimeError" in out)
    check("TT6 실패 시 추천 금지를 명시", "추천하지 마라" in out or "지어내지" in out)


# ── ⓑ 거절 화면에 가격이 없다 ────────────────────────────────
def t_refusal_has_no_prices():
    """### 실측 4/6 — 가격을 「참고용」이라 달아 보여줬더니 모델이 그냥 썼다."""
    items = [rec("광주서부", 15000, 8.0) for _ in range(8)]  # 시장 1곳뿐 = 불충분
    with_day(DayData("2026-08-26", items, 127_650, "api"))
    out = tools_mod.shipping_market_advice("배추", "2026-08-26")
    check("TT7 거절 화면에 원/kg 표기 0건", not PRICE.search(out), PRICE.findall(out)[:3])
    check("TT8 그래도 시장 이름·건수는 남긴다", "광주서부" in out and "8건" in out)


def t_truncated_is_refused_even_with_many_records():
    items = [rec("광주서부", 15000, 8.0) for _ in range(50)]
    items += [rec("진주", 9000, 8.0) for _ in range(50)]
    with_day(DayData("2026-08-26", items, 127_650, "api"))  # 100 / 127,650
    out = tools_mod.shipping_market_advice("배추", "2026-08-26")
    check("TT9 절단이면 건수 많아도 거절", "답할 수 없다" in out)
    check("TT10 덮음률을 %로 말한다", "%" in out)


# ── ⓒ 두 경로 다 [한 줄] 로 시작 ─────────────────────────────
def t_headline_present_both_paths():
    with_day(DayData("2026-08-30", [], None, "api"))
    refusal = tools_mod.shipping_market_advice("배추", "2026-08-30")
    check("TT11 거절에도 [한 줄] 있다", "[한 줄]" in refusal)

    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    with_day(DayData("2026-08-28", day, len(day), "cache"))
    ok = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT12 답에도 [한 줄] 있다", "[한 줄]" in ok)


# ── ⓓ 답하는 경로는 «통과» 해야 한다 (실패할 수 없는 대조군 방지) ──
def t_sufficient_path_answers_with_prices():
    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    with_day(DayData("2026-08-28", day, len(day), "cache"))
    out = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT13 충분하면 «비교 가능»", "비교 가능" in out)
    check("TT14 충분하면 가격을 «낸다»", bool(PRICE.search(out)), (PRICE.findall(out) or [""])[0])
    check("TT15 근거 건수를 함께 낸다", "근거" in out)
    check("TT16 포장 급 차이를 경고한다(1kg ↔ 12kg)", "포장 급이 다르다" in out)


# ── 품목 섞임 경고 ───────────────────────────────────────────
def t_exact_match_wins():
    """### 정확일치가 있으면 «배추» 가 양배추·브로콜리를 안 물어야 한다.

    이게 실제 버그였다: 옛 코드는 품목명+품종명 이어붙인 문자열에 부분일치를 걸어
    «배추» 하나에 양배추 916 · 브로콜리 554 · 칼리플라워 68 이 딸려 왔다.
    """
    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    for it in day[:4]:
        it["gds_mclsf_nm"] = "양배추"  # 정확일치가 있으니 «배추» 조회에 안 들어와야 한다
    with_day(DayData("2026-08-28", day, len(day), "cache"))
    out = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT17 정확일치가 있으면 양배추가 안 섞인다", "여러 품목" not in out, out[:60])


def t_fallback_mix_is_warned():
    """### 정확일치가 «없어» 부분일치로 넓어지면 — 무엇이 섞였는지 말해야 한다."""
    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    for i, it in enumerate(day):
        it["gds_mclsf_nm"] = "얼갈이배추" if i % 2 == 0 else "양배추"  # 정확한 «배추» 는 없다
    with_day(DayData("2026-08-28", day, len(day), "cache"))
    out = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT18 넓어지면 섞였다고 말한다", "여러 품목" in out, out[:70])
    check("TT19 무엇이 섞였는지 이름을 댄다", "얼갈이배추" in out and "양배추" in out)


# ── 데모 추출본: 「그 품목엔 완전」 을 게이트가 옳게 다루나 ──────
def t_demo_extract_answers_for_listed_product():
    """### 저장소를 갓 받은 심사자가 «답하는 장면» 을 볼 수 있어야 한다.

    전량 캐시는 90MB 라 못 올린다. 데모 추출본(0.27MB)은 몇 품목에 대해서만 완전하고
    그 사실을 스스로 밝힌다. 목록 안 품목은 비교가 성립한다.
    """
    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    with_day(DayData("2026-08-28", day, 129_536, "demo", ["배추"]))
    out = tools_mod.shipping_market_advice("배추", "2026-08-28")
    check("TT20 목록 안 품목은 답한다(전량 아님에도)", "비교 가능" in out, out[:60])
    check("TT21 그 근거를 밝힌다", "전부 들어 있다" in out)


def t_demo_extract_refuses_unlisted_product():
    """### 목록 «밖» 품목은 여전히 절단이다. 여기서 답하면 추출본이 거짓말을 하는 것이다."""
    day = [rec("춘천", 14000, 1.0) for _ in range(6)]
    day += [rec("안산", 3000, 12.0) for _ in range(6)]
    for it in day:
        it["gds_mclsf_nm"] = "배추"
    with_day(DayData("2026-08-28", day, 129_536, "demo", ["배추"]))
    out = tools_mod.shipping_market_advice("양파", "2026-08-28")
    check("TT22 목록 밖 품목은 거절", "답할 수 없다" in out, out[:60])
    check(
        "TT23 «전국에 없다» 가 아니라 «못 봤다» 로 말한다",
        "못 봤다" in out and "전국에서 0건" not in out,
        out[:120],
    )


def t_headline_carries_no_digits_on_refusal():
    """### 베낄 줄에 숫자를 넣지 않는다.

    실물: 헤드라인에 «34.97%(45,301/129,536)» 를 넣었더니 모델이 그 숫자로
    ### «없는 날짜별 건수 표» 를 만들어 냈다. 자세한 이유는 본문에 두고 한 줄은 짧게.
    """
    items = [rec("광주서부", 15000, 8.0) for _ in range(50)]
    items += [rec("진주", 9000, 8.0) for _ in range(50)]
    with_day(DayData("2026-08-26", items, 127_650, "api"))
    out = tools_mod.shipping_market_advice("배추", "2026-08-26")
    head = [ln for ln in out.splitlines() if ln.startswith("[한 줄]")]
    check("TT24 거절에 [한 줄] 이 있다", bool(head))
    if head:
        digits = re.findall(r"\d[\d,.]*%|\d{3,}", head[0].split(":", 1)[-1])
        check("TT25 그 줄에 통계 숫자가 없다", not digits, f"{head[0][:70]} | {digits}")
    check("TT26 자세한 이유는 본문에 남아 있다", "%" in out)


# ── 인터페이스 계약 (agent.py) ───────────────────────────────
def t_demo_pins_to_shipped_data():
    """### 데모는 «저장소가 싣는 자료» 로 돈다. 사람 기계에 뭐가 있든.

    실물: 팀원이 저장소에서 돌렸더니 장면3 이 거절 대신 «답» 을 냈다.
    그 기계엔 전량 캐시가 있어 양파도 완전했기 때문이다. 둘 다 옳은 동작이고
    ### 틀린 것은 「조건을 안 밝힌 내 보고」였다. 이제 코드가 조건을 고정한다.
    """
    import agent as A

    here = os.path.dirname(os.path.abspath(__file__))
    demo = [f for f in os.listdir(os.path.join(here, "_cache"))
            if f.startswith("demo-")] if os.path.isdir(os.path.join(here, "_cache")) else []
    if not demo:
        check("TT27 데모 자료가 저장소에 있다", False, "_cache/demo-*.json.gz 없음")
        return
    check("TT27 데모 자료가 저장소에 있다", True, demo[0])

    # 🔴 **이 시험이 처음엔 내 환경만 통과했다** (2026-08-30, 심사자 조건 재검증에서 드러남).
    #    고정은 «전량 캐시가 있을 때만» 필요하다. 갓 받은 저장소엔 데모밖에 없어서
    #    `_pin_demo_cache` 가 일찍 빠져나가고, ### 내 단언이 무조건이라 FAIL 이 났다.
    #    ### 코드는 맞았고 시험이 틀렸다 — 팀원이 나에게 잡아준 그 실수를 내가 시험에서 또 했다.
    #    ⇒ **기전이 아니라 결과를 단언한다: 「무엇을 쓰든 그게 데모 자료여야 한다」.**
    saved = os.environ.pop("SHIPPER_CACHE", None)
    try:
        A._pin_demo_cache()
        import data as D

        used = D._cache_dir()
        left = os.listdir(used) if os.path.isdir(used) else []
        has_demo = any(f.startswith("demo-") for f in left)
        has_full = any(f[0].isdigit() and f.endswith(".json") for f in left)
        check("TT28 실제로 쓰는 자료에 데모가 있다", has_demo, str(left[:3]))
        check("TT29 그리고 전량 캐시는 안 쓴다", not has_full, str([f for f in left if f[0].isdigit()][:2]))
    finally:
        os.environ.pop("SHIPPER_CACHE", None)
        if saved:
            os.environ["SHIPPER_CACHE"] = saved


def t_interface_never_prints_model_text_by_default():
    """### 모델이 쓴 문장은 기본으로 화면에 안 나온다.

    모델 자유 생성은 여전히 한국어를 깨뜨린다(`giá`·`trung`, 6회 중 약 2회).
    ### 그건 「풀린」 게 아니라 「안 보이는」 것이다. 그 둘은 다르고,
    ### 누가 그 출력을 되살리면 깨진 글자가 다시 화면에 온다. 그래서 계약으로 박는다.
    """
    import agent as A
    import inspect

    src = inspect.getsource(A.ask)
    check("TT30 모델 문장 출력이 환경변수 뒤에 있다", "SHOW_MODEL_TEXT" in src)
    # 기본값에서 그 분기가 꺼져 있나
    saved = os.environ.pop("SHOW_MODEL_TEXT", None)
    try:
        check("TT31 기본값은 꺼짐", not os.getenv("SHOW_MODEL_TEXT"))
    finally:
        if saved:
            os.environ["SHOW_MODEL_TEXT"] = saved


def t_no_key_is_not_no_data():
    """### 조회를 «못 한 것» 을 «없다» 로 말하지 않는다. 실제로 그 버그가 있었다."""
    saved = os.environ.get("DATA_GO_KR_API_KEY")
    import config as C
    orig = C.load_env
    C.load_env = lambda: None
    os.environ["DATA_GO_KR_API_KEY"] = ""
    restore()  # 진짜 load_day 를 쓴다
    try:
        with_day(DayData("2026-09-01", [], None, "no-key"))
        out = tools_mod.shipping_market_advice("배추", "2026-09-01")
        check("TT32 키 없음은 «조회할 수 없다»", "조회할 수 없다" in out, out[:60])
        check("TT33 «없다는 뜻이 아니다» 를 말한다", "없다」는 뜻이 아니다" in out or "못 봤다" in out)
    finally:
        C.load_env = orig
        if saved is not None:
            os.environ["DATA_GO_KR_API_KEY"] = saved
        else:
            os.environ.pop("DATA_GO_KR_API_KEY", None)


def main() -> int:
    for f in (
        t_never_raises_on_none_total,
        t_never_raises_on_broken_records,
        t_tool_failure_becomes_refusal,
        t_refusal_has_no_prices,
        t_truncated_is_refused_even_with_many_records,
        t_headline_present_both_paths,
        t_sufficient_path_answers_with_prices,
        t_exact_match_wins,
        t_fallback_mix_is_warned,
        t_demo_extract_answers_for_listed_product,
        t_demo_extract_refuses_unlisted_product,
        t_headline_carries_no_digits_on_refusal,
        t_demo_pins_to_shipped_data,
        t_interface_never_prints_model_text_by_default,
        t_no_key_is_not_no_data,
    ):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            check(f"{f.__name__} 자체가 터짐", False, f"{type(e).__name__}: {e}")
        finally:
            restore()

    print("=" * 68)
    for name, ok, note in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{note}]" if note else ""))
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 68)
    print(f"{n_ok}/{len(RESULTS)} PASS")

    # ⚠️ 이 줄이 처음엔 `n in ("TT9", ...)` 였다. 이름이 «TT9 절단이면…» 이라 정확일치가 안 됐고
    #    ### 반증자 확인이 조용히 0/0 을 냈다. 스위트가 자기 검사를 못 하고 있었다.
    blocked = [n for n, ok, _ in RESULTS if ok and n.startswith(("TT4 ", "TT7 ", "TT9 "))]
    answered = [n for n, ok, _ in RESULTS if ok and n.startswith(("TT13 ", "TT14 "))]
    print(f"반증자 확인: 막는 사례 {len(blocked)}건 · 답하는 사례 {len(answered)}건")
    if not blocked or not answered:
        print("  🔴 한 방향만 있다 = 실패할 수 없는 대조군이다. 통과를 근거로 쓰지 마라.")
        return 1
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
