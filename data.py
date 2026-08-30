"""
데이터 층 — **얼마나 봤는지를 항상 함께 돌려준다**

우리가 실제로 당한 오독이 만든 규율: 레코드만 돌려주면 받는 쪽이 «이게 전부» 라고 오해한다.
### 그래서 이 층은 «몇 건 받았나» 와 «그날 전체가 몇 건인가» 를 «같이» 돌려준다.
   그 둘이 있어야 Coverage 가 절단을 판정할 수 있다.

두 경로:
  ⓐ **캐시** — 전량이 디스크에 있으면 그걸 쓴다. 덮음률 100% ⇒ 게이트가 비교를 허용한다.
  ⓑ **예산 조회** — 대화 중에는 13만건을 못 받는다. 페이지 예산만큼 받고
     ### «절단됐다» 를 숨기지 않고 그대로 돌려준다 ⇒ 게이트가 비교를 «막는다».

### 이 둘의 차이가 우리 데모다 — 같은 질문에 한 번은 답을 안 하고 한 번은 답한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx

from config import CACHE_DIR, api_key

API = "https://apis.data.go.kr/B552845/katRealTime2/trades2"


def _cache_dir() -> str:
    """### 캐시 위치를 «호출 시점» 에 읽는다.

    🔴 처음엔 import 시점에 굳혔다(`CACHE = str(CACHE_DIR)`).
       그러면 `agent.py` 가 실행 중에 `SHIPPER_CACHE` 를 바꿔도 **안 먹는다** —
       `tools` 가 이미 import 되면서 이 값을 잡아버렸기 때문이다.
       ### 실제로 안 먹었다. 데모를 데모 자료에 고정하려던 것이 조용히 무시됐다.
    """
    v = os.getenv("SHIPPER_CACHE")
    return v if v else str(CACHE_DIR)
DEFAULT_PAGE_BUDGET = 3  # 대화 중 기본. 3,000건 = 하루의 약 2%


def _key() -> str:
    return api_key()


@dataclass
class DayData:
    date: str
    items: list[dict]
    day_total: int | None
    source: str  # "cache" | "demo" | "api"
    complete_products: list[str] | None = None

    @property
    def complete(self) -> bool:
        return self.day_total is not None and len(self.items) >= self.day_total

    def complete_for(self, product: str) -> bool:
        """### 이 자료가 «그 품목에 대해» 완전한가.

        전량이면 당연히 완전하다. 전량이 아니어도, 그 품목의 그날 기록을 «전부» 가졌다면
        ### **그 품목에 대해 못 본 시장은 없다** ⇒ 비교가 성립한다.
        (데모 추출본이 이 경우다. 목록 밖 품목은 여전히 절단이고 게이트가 막는다.)
        """
        if self.complete:
            return True
        if not self.complete_products:
            return False
        p = product.strip()
        return any(p == c or p in c for c in self.complete_products)


def _cache_path(date: str) -> str:
    return os.path.join(_cache_dir(), f"{date}.json")


def _page(date: str, page: int, rows: int = 1000) -> tuple[list[dict], int | None]:
    r = httpx.get(
        API,
        params={
            "serviceKey": _key(),
            "returnType": "json",
            "pageNo": str(page),
            "numOfRows": str(rows),
            "cond[trd_clcln_ymd::EQ]": date,
        },
        timeout=60.0,
    )
    if r.status_code != 200:
        return [], None
    body = (r.json().get("response", {}) or {}).get("body", {}) or {}
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    try:
        total = int(body.get("totalCount") or 0) or None
    except (TypeError, ValueError):
        total = None
    return items, total


def day_total_only(date: str) -> int | None:
    """그날 전체 건수만. 1행만 받아 싸게."""
    _, total = _page(date, 1, rows=1)
    return total


def _demo_path(date: str) -> str:
    return os.path.join(_cache_dir(), f"demo-{date}.json.gz")


def load_day(date: str, page_budget: int = DEFAULT_PAGE_BUDGET) -> DayData:
    """전량 캐시 → 데모 추출본 → 예산 조회 순. **어느 쪽이든 day_total 을 함께 준다.**"""
    p = _cache_path(date)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            items = json.load(f)
        # 캐시는 전량일 때만 저장된다(measure_unit_effect 규약).
        return DayData(date, items, len(items), "cache")

    # ### 저장소에 올라가는 작은 추출본. 자기가 «어느 품목에 대해 완전한지» 를 들고 있다.
    dp = _demo_path(date)
    if os.path.exists(dp):
        import gzip

        with gzip.open(dp, "rt", encoding="utf-8") as f:
            payload = json.load(f)
        return DayData(
            date,
            payload.get("records", []),
            payload.get("day_total"),
            "demo",
            payload.get("complete_products") or [],
        )

    # 🔴 **조회를 「못 한 것」과 「해서 0건인 것」은 다르다** (2026-08-30 실측 버그).
    #    키가 없으면 API 가 아무것도 안 주고, 그러면 게이트가 «그날 전국 경매 기록이 없다» 고
    #    ### 단언했다. **우리가 이 프로젝트에서 제일 경계하는 그 혼동이다.**
    #    ⇒ 조회 자체가 불가능하면 그 사실을 `source` 에 실어 위로 올린다.
    if not _key():
        return DayData(date, [], None, "no-key")

    out: list[dict] = []
    total: int | None = None
    for pg in range(1, max(1, page_budget) + 1):
        items, t = _page(date, pg)
        if t is not None:
            total = t
        if not items:
            break
        out.extend(items)
        if total and len(out) >= total:
            break
    if total is None:
        total = day_total_only(date)
    return DayData(date, out, total, "api")


def _mclsf(it: dict) -> str:
    return (it.get("gds_mclsf_nm") or "").strip()


def filter_product(items: list[dict], keyword: str) -> list[dict]:
    """품목으로 고른다. ### 이름이 겹친다고 같은 작물이 아니다.

    🔴 **처음엔 「품목명+품종명」 이어붙인 문자열에 부분일치를 걸었다. 틀렸다** (2026-08-30 실측):
      · `"배추"` 로 물으면 **얼갈이배추 1,531 · 배추 1,423 · 양배추 916 ·
        브로콜리(녹색꽃양배추) 554 · 칼리플라워(꽃양배추) 68** 이 한 덩어리로 잡혔다.
        ### **브로콜리 값과 배추 값을 같은 표에 놓고 「어느 시장이 비싸다」를 냈다.**
      · `"사과"` 는 **대추 31건**을 물고 왔다 — 품종명이 `사과대추` 라서.
      · 이 오염이 시장 격차를 부풀렸다(배추 격차가 1030% 로 나왔다).

    ### ⇒ **품목명(`gds_mclsf_nm`) 정확일치를 먼저 본다.** 있으면 그것만 쓴다.
    없을 때만 부분일치로 넓히고, ### **그때는 무엇이 섞였는지 호출자에게 보인다**
    (`matched_products()` 로 세어 caveat 에 싣는다).
    """
    kw = keyword.strip()
    exact = [it for it in items if _mclsf(it) == kw]
    if exact:
        return exact
    # 정확일치가 없을 때만 넓힌다. 넓혔다는 사실은 숨기지 않는다.
    return [it for it in items if kw in _mclsf(it)]


def matched_products(items: list[dict]) -> dict[str, int]:
    """고른 결과에 «어떤 품목» 이 몇 건씩 들었나. 섞였으면 그대로 보여준다."""
    out: dict[str, int] = {}
    for it in items:
        n = _mclsf(it)
        if n:
            out[n] = out.get(n, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def cached_dates() -> list[str]:
    """비교가 성립할 수 있는 날짜.

    🔴 처음엔 전량 캐시(`*.json`)만 셌다. ### **갓 받은 저장소에는 그게 없다** —
       저장소가 싣는 건 데모 추출본(`demo-*.json.gz`)이라 «없다» 가 나왔다.
       심사자가 첫 화면에서 «쓸 수 있는 날짜가 없다» 를 보게 된다.
    ⇒ 둘 다 센다. **다만 성격이 다르니 구별해서 돌려준다**(`cached_dates_detail`).
    """
    return [d for d, _ in cached_dates_detail()]


def cached_dates_detail() -> list[tuple[str, list[str] | None]]:
    """(날짜, 완전한 품목 목록) — 전량이면 목록이 None."""
    if not os.path.isdir(_cache_dir()):
        return []
    out: list[tuple[str, list[str] | None]] = []
    for f in sorted(os.listdir(_cache_dir())):
        if f.endswith(".json") and not f.startswith("demo-"):
            out.append((f[:-5], None))  # 전량
        elif f.startswith("demo-") and f.endswith(".json.gz"):
            date = f[len("demo-") : -len(".json.gz")]
            if any(d == date and c is None for d, c in out):
                continue  # 전량이 이미 있으면 그쪽이 낫다
            try:
                import gzip

                with gzip.open(os.path.join(_cache_dir(), f), "rt", encoding="utf-8") as fh:
                    payload = json.load(fh)
                out.append((date, payload.get("complete_products") or []))
            except Exception:  # noqa: BLE001 — 못 읽으면 없는 것으로 둔다
                continue
    return sorted(out, key=lambda x: x[0])
