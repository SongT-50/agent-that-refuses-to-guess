"""
데모 캐시 만들기 — **심사자가 저장소를 받자마자 「답하는 장면」을 볼 수 있게**

문제 (2026-08-30 발견):
  전량 캐시가 하루 **90MB** 라 저장소에 못 올린다. `.gitignore` 로 빠져 있다.
  ### ⇒ 저장소를 갓 받으면 캐시가 없고, 그러면 **에이전트가 거절만 한다.**
  해커톤 요건이 *"setup instructions needed to run the project"* 이고 심사자가 돌려볼 수 있다.
  ### **우리 제품이 「아무것도 못 하는 것」처럼 보인다.**

그런데 품목을 골라 담으면 게이트에 거짓말을 하게 된다:
  게이트는 `day_total` 로 절단을 판정한다. 골라 담은 걸 «전량» 이라 우기면
  ### **우리가 비판하는 그 짓을 우리가 하는 것이다.**

⇒ 그래서 캐시가 **스스로 밝힌다**:
  · `day_total`          = 그날 «진짜» 전체 건수 (129,536)
  · `complete_products`  = ### 이 추출본이 «완전한» 품목 목록
  · `records`            = 그 품목들의 그날 전 기록

### 근거: 어떤 품목의 그날 기록을 «전부» 가졌다면, 그 품목에 대해 못 본 시장은 없다.
   그래서 그 품목만 비교가 성립한다. 목록 밖 품목은 여전히 절단이고 게이트가 막는다.

쓰기:  python build_demo_cache.py 2026-08-28
"""
from __future__ import annotations

import gzip
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CACHE_DIR  # noqa: E402
from data import load_day  # noqa: E402

# 데모에 쓸 품목. 적을수록 파일이 작다.
DEMO_PRODUCTS = ["복숭아", "배추", "사과", "포도"]
KEEP = [
    "whsl_mrkt_nm",
    "scsbd_prc",
    "unit_qty",
    "qty",
    "gds_mclsf_nm",
    "gds_sclsf_nm",
]


def demo_path(date: str) -> str:
    return os.path.join(str(CACHE_DIR), f"demo-{date}.json.gz")


def build(date: str) -> int:
    day = load_day(date)
    if not day.complete:
        print(f"🔴 {date} 전량 캐시가 없다. 먼저 measure_unit_effect.py 로 받아라.")
        print(f"   (지금 {len(day.items):,}건 / 전체 {day.day_total})")
        return 1

    recs = [
        {k: it.get(k) for k in KEEP}
        for it in day.items
        if (it.get("gds_mclsf_nm") or "").strip() in DEMO_PRODUCTS
    ]
    payload = {
        "date": date,
        "day_total": day.day_total,  # ### 그날 «진짜» 전체. 골라 담았다고 줄이지 않는다
        "complete_products": DEMO_PRODUCTS,
        "note": (
            "이 추출본은 complete_products 목록의 품목에 대해서만 완전하다. "
            "목록 밖 품목은 여기 없다고 해서 그날 없었던 것이 아니다."
        ),
        "records": recs,
    }
    os.makedirs(str(CACHE_DIR), exist_ok=True)
    p = demo_path(date)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    size = os.path.getsize(p)
    print(f"✅ {p}")
    print(f"   {len(recs):,}건 · {size/1e6:.2f} MB · 품목 {', '.join(DEMO_PRODUCTS)}")
    print(f"   day_total = {day.day_total:,} (진짜 전체. 이 파일이 담은 건 그중 일부다)")
    return 0


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "2026-08-28"
    sys.exit(build(d))
