"""절단 확인 — measure_unit_effect 의 10페이지 상한이 데이터를 잘랐나."""
import os
import sys

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


def body_of(page: str, rows: str) -> dict:
    r = httpx.get(
        API,
        params={
            "serviceKey": KEY,
            "returnType": "json",
            "pageNo": page,
            "numOfRows": rows,
            "cond[trd_clcln_ymd::EQ]": DATE,
        },
        timeout=90.0,
    )
    return (r.json().get("response", {}) or {}).get("body", {}) or {}


b = body_of("1", "10")
total = b.get("totalCount")
print(f"totalCount 신고값 : {total}")

for p in ("10", "11", "20", "34"):
    bb = body_of(p, "1000")
    it = bb.get("items", [])
    if isinstance(it, dict):
        it = it.get("item", [])
    print(f"page {p:>3} (1000행 요청) → 실제 {len(it)}건")

print()
print("판정:")
print("  page 11+ 에 데이터가 있으면 → 내 10페이지 상한이 «절단» 이다. 결과가 편향됐을 수 있다.")
print("  page 11 이 0건이면          → 하루가 10,000건 언저리라 절단이 아니다.")
