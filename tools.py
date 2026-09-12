"""
Strands 도구 — **도구가 완성된 답을 준다. 모델은 두 문장만 쓴다.**

실측: 한 턴에서 ### 시간의 89% 가 «최종 답 생성» 이고, 출력 길이와 강하게 붙어 있다
(Spearman 0.833 · 한글 100자에 5.6초).
⇒ ### 모델에게 표를 다시 타이핑시키면 그만큼 느려진다. 그래서 도구가 «읽을 수 있는 완성본» 을 주고
   시스템 프롬프트가 «다시 쓰지 마라» 고 말한다. 이건 취향이 아니라 실측에 따른 설계다.

그리고 판정은 여기서 한다(B축 우선). 모델은 판정을 «전달» 할 뿐 «생산» 하지 않는다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strands import tool  # noqa: E402

from data import (  # noqa: E402
    cached_dates,
    cached_dates_detail,
    filter_product,
    load_day,
    matched_products,
)
from evidence import Evidence, build_evidence, render  # noqa: E402


# ### 마지막 판정의 «구조화된 근거». 웹 UI 가 표를 그릴 때 쓴다 (2026-09-12).
#   모델은 도구가 낸 텍스트만 본다. UI 는 같은 호출이 만든 Evidence 객체를 본다.
#   ⇒ 화면의 표와 모델이 읽은 문장은 «같은 계산» 에서 나온다. 두 번 계산하지 않는다.
#   ⚠️ 한 프로세스에 한 요청씩 돈다는 전제(web.py 가 lock 으로 보장). 동시 요청이면 섞인다.
LAST: dict = {}


def _remember(**kw) -> None:
    LAST.clear()
    LAST.update(kw)


def _hl(text: str) -> str | None:
    """도구 텍스트의 [한 줄] 만 꺼낸다. ### headline 과 Evidence 가 «같은 호출» 에서 나왔음을 보증하려고
    여기서 함께 기억한다(CO M3 — 메시지에서 따로 고른 문자열과 전역 LAST 를 합치지 않는다)."""
    for line in text.splitlines():
        if line.startswith("[한 줄]"):
            return line[len("[한 줄]"):].strip()
    return None


@tool
def shipping_market_advice(product: str, date: str = "") -> str:
    """출하할 품목을 «어느 도매시장에 내면 유리한가» 판정한다.

    근거가 모자라면 답을 지어내지 않고 왜 답할 수 없는지를 돌려준다.

    Args:
        product: 품목 이름 (예: 배추, 사과, 양파, 복숭아)
        date: 정산일 YYYY-MM-DD. 비우면 자료가 갖춰진 최근 날짜.
    """
    # 🔴 **도구가 죽으면 모델이 지어낸다. 실측으로 확인했다** (2026-08-30):
    #    `day_total` 이 None 인 날(자료 0건)에 `{:,}` 포맷이 TypeError 를 냈다.
    #    ### 도구는 죽었는데 모델은 유창한 한국어로 **없는 시장과 가격을 만들어 냈다**
    #    ("경양시" · "전주시장 0.58 달러" · "서산시장 8000원").
    #    ⇒ ### **예외를 「거절」로 바꾼다.** 도구 실패가 침묵이 되면 그 자리를 환각이 채운다.
    #    = 우리 원칙 그대로 — 비어 있지 않은 텍스트는 유효한 결과의 증거가 아니다.
    try:
        return _advice(product, date)
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 «거절» 로 바꾼다
        text = (
            f"[한 줄] {date or '해당 날짜'} {product}: 답할 수 없다 — "
            f"자료 조회 중 오류가 났다({type(e).__name__}).\n\n"
            "[근거] 판정 불가 — 도구가 실패했다. ### 추천하지 마라. "
            "값을 지어내지 말고 이 사실을 그대로 전할 것."
        )
        _remember(product=product, date=date, evidence=None, error=type(e).__name__, headline=_hl(text))
        return text


def _advice(product: str, date: str = "") -> str:
    if not date:
        ds = cached_dates()
        if not ds:
            text = (
                f"[한 줄] {product}: 답할 수 없다 — 전량 자료가 준비된 날짜가 없다.\n\n"
                "[근거] 판정 불가 — 전량 자료가 준비된 날짜가 없다.\n"
                "날짜를 지정하면 그날 자료를 조회하되, 대화 중에는 일부만 받으므로 "
                "시장 비교는 못 하고 참고 수치만 낸다."
            )
            _remember(product=product, date=date, evidence=None, error="no-dates", headline=_hl(text))
            return text
        date = ds[-1]

    day = load_day(date)

    # ### 조회 자체를 «못 한» 경우. 「없다」로 말하면 안 된다.
    if day.source == "no-key":
        text = "\n".join(
            [
                f"[한 줄] {date} {product}: 답할 수 없다 — 자료를 조회할 수 없다 "
                "(API 키가 없고 그날 캐시도 없다).",
                "",
                "[근거] 판정 불가 — ### 그날 기록이 「없다」는 뜻이 아니다. "
                "우리가 「못 봤다」는 뜻이다.",
                "  · 저장소에 실린 데모 자료의 날짜를 물으면 키 없이도 답한다.",
                "  · 다른 날짜를 보려면 DATA_GO_KR_API_KEY 가 필요하다(data.go.kr 무료).",
            ]
        )
        _remember(product=product, date=date, evidence=None, error="no-key", source=day.source, headline=_hl(text))
        return text

    matched = filter_product(day.items, product)
    ev = build_evidence(
        matched,
        product,
        date,
        day_total=day.day_total,
        all_day_items=day.items,
        product_complete=day.complete_for(product),
    )
    # ### `day_total` 은 None 일 수 있다(그날 자료가 아예 없을 때). 포맷에 그냥 넣으면 죽는다.
    tot = f"{day.day_total:,}건" if day.day_total else "총계 미상"
    head = f"(자료: {day.source} · 그날 {tot} 중 {len(day.items):,}건 확보)\n"

    # ### 여러 품목이 섞였으면 숨기지 않는다 — «배추» 가 브로콜리를 물고 온 적이 있다.
    mix = matched_products(matched)
    if len(mix) > 1:
        parts = ", ".join(f"{k} {v:,}건" for k, v in list(mix.items())[:5])
        more = f" 외 {len(mix) - 5}종" if len(mix) > 5 else ""
        head += (
            f"⚠️ '{product}' 로 여러 품목이 잡혔다: {parts}{more}\n"
            f"   서로 다른 작물이면 이 비교는 성립하지 않는다. 품목을 좁혀 다시 물을 것.\n"
        )
    body = render(ev)
    # ### headline 과 Evidence 를 «한 호출의 한 단위» 로 기억한다 (CO M3).
    _remember(
        product=product, date=date, evidence=ev, error=None, headline=_hl(body),
        source=day.source, day_total=day.day_total, fetched=len(day.items), mix=mix,
    )
    return head + body


def last_as_dict(top_n: int = 8) -> dict:
    """마지막 판정을 JSON 으로. ### 판정·근거·경고 전부 evidence.py 가 낸 것을 옮길 뿐, 여기서 다시 계산하지 않는다."""
    if not LAST:
        return {}
    ev: Evidence | None = LAST.get("evidence")
    out = {
        "product": LAST.get("product"),
        "date": LAST.get("date"),
        "source": LAST.get("source"),
        "day_total": LAST.get("day_total"),
        "fetched": LAST.get("fetched"),
        "error": LAST.get("error"),
        "mix": LAST.get("mix") or {},
    }
    if ev is None:
        return out
    u = ev.usable_markets
    out.update(
        {
            "sufficient": ev.sufficient,
            "n_total": ev.n_total,
            "n_markets": len(ev.markets),
            "n_usable": len(u),
            "why_insufficient": ev.why_insufficient(),
            "caveats": ev.caveats(),
            "coverage": (
                {
                    "fetched": ev.coverage.fetched,
                    "day_total": ev.coverage.day_total,
                    "markets_seen": ev.coverage.markets_seen,
                    "markets_nationwide": ev.coverage.markets_nationwide,
                    "product_complete": ev.coverage.product_complete,
                    "truncated": ev.coverage.truncated,
                }
                if ev.coverage
                else None
            ),
            # ### 거절이면 가격을 «안 보낸다» — render() 가 텍스트에서 뺀 것과 같은 이유.
            #   비교가 성립하지 않는 표본의 값이 화면에 있으면 사람도 그걸 인용한다.
            "markets": [
                {
                    "rank": i,
                    "market": m.market,
                    "won_per_kg_median": round(m.won_per_kg_avg),
                    "won_per_kg_mean": round(m.mean_raw),
                    "n": m.n,
                    "typical_pack_kg": m.typical_pack,
                    "total_qty": round(m.total_qty),
                    "skewed": m.skewed,
                    "mixed_pack": m.mixed_pack,
                }
                for i, m in enumerate(u[:top_n], 1)
            ]
            if ev.sufficient
            else [],
            "markets_seen": [{"market": m.market, "n": m.n} for m in ev.markets[:12]],
        }
    )
    return out


@tool
def available_dates() -> str:
    """시장 비교가 성립하는 날짜와 품목. ### 무엇까지 되는지 «먼저» 알려준다."""
    detail = cached_dates_detail()
    if not detail:
        return (
            "[한 줄] 비교 가능한 날짜가 없다 — 자료를 먼저 받아야 한다.\n"
            "날짜를 지정하면 조회는 되지만 하루의 일부만 받으므로 시장 비교는 못 한다.\n"
            "전량을 받으려면: python measure_unit_effect.py"
        )
    lines = ["[한 줄] 비교 가능: " + ", ".join(d for d, _ in detail), ""]
    for d, products in detail:
        if products is None:
            lines.append(f"  {d}: 전량 — 모든 품목 비교 가능")
        else:
            lines.append(
                f"  {d}: 데모 추출본 — {', '.join(products)} 만 비교 가능"
                " (그 밖 품목은 «못 봤다» 로 거절한다)"
            )
    return "\n".join(lines)


# ### 모델에게 주는 지시. 위 89%(출력 길이)를 겨눈다.
#
# 🔴 **영어로 쓴다 — 다만 근거는 내가 처음 쓴 것과 다르다** (2026-08-30, 정정본):
#    처음엔 *"한국어 프롬프트에서는 도구가 실행되지 않는다"* 고 적었다. ### **틀렸다.**
#    그건 **조건마다 1회씩** 재고 내린 결론이었고, 6회씩 재니 **한국어 5/6 · 영어 6/6** 이었다.
#    ⇒ ### **언어가 켜고 끄는 스위치가 아니다. 간헐적 실패이고 영어가 조금 낫다.**
#    ### 진짜 원인은 다른 데 있었다 — `agent.py` 의 **기본 callback_handler**(아래 참조).
#    ⚠️ llama3.2:3b · n=6 에서만 쟀다.
SYSTEM_PROMPT = """You are a shipping advisor for Korean agricultural wholesale markets.

Rules:
1. The tool output begins with a line marked [한 줄]. That line IS the answer.
   Reply with that line, in Korean, essentially verbatim. Do not rephrase it.
2. Add nothing else. Do NOT retype tables or numbers — the user already sees the tool output.
3. Never invent markets or prices that are not in the tool output.
"""

ALL_TOOLS = [shipping_market_advice, available_dates]
