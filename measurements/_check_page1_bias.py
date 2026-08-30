"""
🔴 결정적 확인 — **기존 MCP 도구가 보는 1,000건이 하루를 대표하나**

`compare_market_prices` 는 `numOfRows=1000` 으로 «한 페이지만» 받아 거기서 품목을 거른다.
하루는 129,536건이다. ⇒ 0.77%.

물음은 «적게 본다» 가 아니라 ### «그 0.77% 가 편향돼 있나» 다.
   고르게 섞여 있으면 → 표본이 작을 뿐이고 시장 비교는 그런대로 성립한다.
   시장·시간 순으로 정렬돼 있으면 → ### 특정 시장만 보인다. 시장 비교가 무의미해진다.

API 호출 3번. 비용 0.
"""
import os
import sys
from collections import Counter

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import api_key  # noqa: E402

KEY = api_key()
API = "https://apis.data.go.kr/B552845/katRealTime2/trades2"
DATE = "2026-08-28"


def page(n: int, rows: int = 1000) -> list[dict]:
    r = httpx.get(
        API,
        params={
            "serviceKey": KEY,
            "returnType": "json",
            "pageNo": str(n),
            "numOfRows": str(rows),
            "cond[trd_clcln_ymd::EQ]": DATE,
        },
        timeout=90.0,
    )
    b = (r.json().get("response", {}) or {}).get("body", {}) or {}
    it = b.get("items", [])
    if isinstance(it, dict):
        it = it.get("item", [])
    return it


def summarize(tag: str, items: list[dict]) -> Counter:
    mk = Counter((it.get("whsl_mrkt_nm") or "?").strip() for it in items)
    print(f"\n[{tag}] {len(items)}건 · 시장 {len(mk)}종")
    for m, c in mk.most_common(6):
        print(f"    {m:14s} {c:5d}건 ({c/len(items)*100:4.1f}%)")
    if len(mk) > 6:
        print(f"    ... 외 {len(mk)-6}종")
    return mk


def main() -> int:
    if not KEY:
        print("키 없음")
        return 1

    p1 = page(1)
    p60 = page(60)
    p130 = page(130)

    m1 = summarize("page 1  = 기존 도구가 보는 그 1,000건", p1)
    m60 = summarize("page 60 = 하루 한가운데", p60)
    m130 = summarize("page 130 = 하루 끝", p130)

    print("\n" + "=" * 66)
    print("판정")
    print("=" * 66)
    print(f"  page 1 이 담은 시장 수   : {len(m1)}")
    print(f"  page 60 이 담은 시장 수  : {len(m60)}")
    print(f"  page 130 이 담은 시장 수 : {len(m130)}")

    only1 = set(m1) - set(m60) - set(m130)
    miss1 = (set(m60) | set(m130)) - set(m1)
    print(f"\n  page1 에만 있는 시장 : {sorted(only1) or '없음'}")
    print(f"  ### page1 이 «못 보는» 시장 : {sorted(miss1) or '없음'}")

    if miss1:
        print(
            f"\n  🔴 편향 확인 — 기존 도구는 {len(miss1)}개 시장을 «구조적으로 못 본다».\n"
            "     ⇒ 그 도구의 «시장 비교» 는 하루의 일부만 놓고 한 비교다."
        )
    else:
        print("\n  ✅ page1 이 다른 페이지의 시장을 다 담는다 ⇒ 시장 편향은 이 표본에선 안 보인다.")
    print("\n⚠️ 페이지 3장만 봤다. 전량 대조는 measure_unit_effect 쪽 캐시로 따로 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
