"""
실측 — **규격 섞임이 진짜 순위를 바꾸나**

합성 시험(EG11)은 "바뀔 수 있다" 까지만 말한다. 실제 데이터에서 얼마나 자주 바뀌는지는 다른 질문이다.
안 재고 "기존 도구가 틀렸다" 고 말하면 그건 우리가 계속 잡는 그 형태다.

방법: data.go.kr 원본을 직접 받아, 같은 품목에 대해
  ⓐ 원단가 평균 순위 (기존 compare_market_prices 방식)
  ⓑ 원/kg 평균 순위 (우리 방식)
두 순위가 다른 날·품목이 몇 건인지 센다.

비용 0 (공공 API). LLM 안 씀.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from config import api_key  # noqa: E402
from evidence import MIN_RECORDS_PER_MARKET, build_evidence  # noqa: E402

KEY = api_key()
API = "https://apis.data.go.kr/B552845/katRealTime2/trades2"

DATES = ["2026-08-27", "2026-08-28"]
PRODUCTS = ["배추", "사과", "감자", "양파", "토마토", "포도", "복숭아", "오이"]

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")

# 🔴 1차 측정은 페이지 상한 10 (=10,000건) 이었다. 실제 하루는 129,536건.
#    ⇒ 7.7% 만 보고 «35.9% 가 뒤바뀐다» 고 냈다. 그 수는 폐기했다.
#    분모를 안 재고 낸 측정은 측정이 아니다. 이제 totalCount 까지 전부 받는다.


def fetch_day(date: str) -> list[dict]:
    """그날 전국 경매 기록 **전량**. totalCount 를 읽고 끝까지 받는다."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{date}.json")
    if os.path.exists(path):
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  [{date}] 캐시 {len(data):,}건")
        return data

    out: list[dict] = []
    total = None
    page = 1
    while True:
        try:
            r = httpx.get(
                API,
                params={
                    "serviceKey": KEY,
                    "returnType": "json",
                    "pageNo": str(page),
                    "numOfRows": "1000",
                    "cond[trd_clcln_ymd::EQ]": date,
                },
                timeout=90.0,
            )
            if r.status_code != 200:
                print(f"  [{date} p{page}] HTTP {r.status_code} — 중단")
                break
            body = (r.json().get("response", {}) or {}).get("body", {}) or {}
        except Exception as e:
            print(f"  [{date} p{page}] 실패: {type(e).__name__} — 중단")
            break
        if total is None:
            total = int(body.get("totalCount") or 0)
            print(f"  [{date}] totalCount={total:,} → {-(-total // 1000)}페이지")
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if not items:
            break
        out.extend(items)
        if page % 25 == 0:
            print(f"    ... {len(out):,}/{total:,}")
        if total and len(out) >= total:
            break
        page += 1

    # ⚠️ 절단 여부를 «조용히» 넘기지 않는다.
    if total and len(out) < total:
        print(f"  🔴 [{date}] 절단: {len(out):,}/{total:,} ({len(out)/total*100:.1f}%)")
    else:
        print(f"  ✅ [{date}] 전량 {len(out):,}건")
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
    return out


def raw_rank(items: list[dict], keyword: str) -> list[tuple[str, float, int]]:
    """기존 방식 — 원단가를 그냥 평균."""
    agg = defaultdict(list)
    for it in items:
        name = f"{it.get('gds_mclsf_nm','')}{it.get('gds_sclsf_nm','')}"
        if keyword not in name:
            continue
        m = (it.get("whsl_mrkt_nm") or "").strip()
        try:
            p = float(it.get("scsbd_prc", 0))
        except (TypeError, ValueError):
            continue
        if m and p > 0:
            agg[m].append(p)
    out = [(m, sum(v) / len(v), len(v)) for m, v in agg.items() if len(v) >= MIN_RECORDS_PER_MARKET]
    out.sort(key=lambda x: -x[1])
    return out


def main() -> int:
    if not KEY:
        print("API 키 없음 — 중단")
        return 1

    flips = 0
    compared = 0
    mixed_cases = 0
    detail = []

    for date in DATES:
        items = fetch_day(date)
        print(f"[{date}] 원본 {len(items):,}건")
        if not items:
            continue
        for kw in PRODUCTS:
            subset = [
                it
                for it in items
                if kw in f"{it.get('gds_mclsf_nm','')}{it.get('gds_sclsf_nm','')}"
            ]
            if not subset:
                continue
            ev = build_evidence(subset, kw, date)
            if not ev.sufficient:
                continue
            rr = raw_rank(subset, kw)
            if len(rr) < 2:
                continue
            compared += 1

            ours = [m.market for m in ev.usable_markets]
            theirs = [m for m, _, _ in rr]
            common = [m for m in theirs if m in ours]
            if len(common) < 2:
                continue

            any_mixed = any(m.mixed_pack for m in ev.usable_markets)
            if any_mixed:
                mixed_cases += 1

            # 1위가 뒤바뀌었나 (출하자에게 실제로 중요한 것)
            top_ours = ours[0]
            top_theirs = next((m for m in theirs if m in ours), None)
            if top_theirs and top_ours != top_theirs:
                flips += 1
                detail.append((date, kw, top_theirs, top_ours, any_mixed))

    print("\n" + "=" * 70)
    print("실측 결과 — 규격 섞임이 순위를 바꾸나")
    print("=" * 70)
    print(f"비교 가능했던 (날짜×품목) 쌍 : {compared}")
    print(f"그중 규격이 섞인 쌍          : {mixed_cases}")
    print(f"### 1위가 뒤바뀐 쌍          : {flips}")
    if compared:
        print(f"    뒤바뀜 비율             : {flips / compared * 100:.1f}%")
    if detail:
        print("\n뒤바뀐 사례 (원단가 1위 → 원/kg 1위):")
        for d, kw, a, b, mx in detail[:20]:
            print(f"  {d} {kw:6s} : {a} → {b}" + ("  [규격 섞임]" if mx else ""))
    else:
        print("\n뒤바뀐 사례 없음.")
        print("### ⇒ 그러면 «기존 방식이 실무에서 틀린다» 고 말할 근거가 이 표본엔 없다.")
    print(f"\n⚠️ 표본 = 날짜 {len(DATES)} × 품목 {len(PRODUCTS)}. 이 밖은 안 쟀다.")
    print("⚠️ 1차 측정(35.9%)은 하루 7.7%만 본 절단 표본이라 폐기했다. 위 수는 전량 기준이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
