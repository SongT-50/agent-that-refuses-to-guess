"""
출하자 판단 에이전트 — **근거 게이트 (결정론적. LLM 안 씀)**

왜 이게 본체인가:
  ### 근거가 늘 충분하지는 않다. 어떤 날 어떤 품목은 비교가 성립하지 않는다.
  그리고 ### 「없다」와 「못 봤다」는 다르다 — 우리가 처음에 그것을 섞었다.
    실물: 배추 하루치가 «2개 시장 5건» 으로 보였다. 데이터가 얇아서가 아니라
    ### 도구가 하루의 0.77% 만 받아 거기서 걸렀기 때문이다(아래 Coverage 참조).
  ⇒ 그때 에이전트는 "모른다" 고 말해야 하고, ### 「무엇을 못 봤는지」까지 말해야 한다.

그런데 그걸 프롬프트로 부탁하면 모델 기분에 달린다.
### 그래서 충분성 판정을 코드에 둔다. 도구가 "불충분" 을 반환하면 모델은 자신 있게 답할 수가 없다.
= 우리 B축(구조) 우선 원칙. 모델은 문장만 짓고, 판정은 여기서 한다.

### 그리고 하나 더 — 단위를 맞춘다.
경매 단가는 포장 단위마다 다르다(10kg 상자 6,000원 ↔ 15kg 상자 40,000원).
규격을 안 맞추고 평균 내면 "싼 시장" 이 실은 작은 상자였을 뿐일 수 있다.
⇒ 여기서는 전부 **원/kg** 로 환산해서 비교한다. 환산 불가한 건은 버리지 않고 따로 센다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any

# ─── 충분성 임계 ─────────────────────────────────────────────
# 아래를 못 넘으면 비교 주장을 하지 않는다.
# ⚠️ 이 숫자들은 «우리가 정한 것» 이지 «측정으로 도출한 것» 이 아니다. 바꿀 때 근거를 적을 것.
MIN_MARKETS = 2  # 시장 비교를 말하려면 최소 2곳
MIN_RECORDS_PER_MARKET = 3  # 한 시장 평균을 말하려면 최소 3건
MIN_TOTAL_RECORDS = 6  # 전체 최소 건수


@dataclass
class MarketStat:
    market: str
    n: int  # 환산 성공 건수
    n_dropped: int  # 단위 없어 환산 못 한 건수
    won_per_kg_avg: float  # ### 중앙값이다. 이름은 호환 위해 둔다 (아래 주석)
    won_per_kg_min: float
    won_per_kg_max: float
    total_qty: float
    pack_sizes: set = field(default_factory=set)  # 섞인 포장 규격들
    varieties: set = field(default_factory=set)
    mean_raw: float = 0.0  # 평균(참고). 중앙과 벌어지면 꼬리가 있다는 신호

    @property
    def skewed(self) -> bool:
        """### 평균이 중앙과 크게 벌어지면 한두 건이 그 시장을 끌고 있다.

        실물: 2026-08-28 복숭아 광주각화 — 656건 중 **kg당 500,005원** 한 건이
        그 시장 평균을 3,669 → 2,911 로 바꾼다(21%). 순위가 통째로 움직인다.
        ⇒ 경락가는 꼬리가 길다. **평균이 아니라 중앙값으로 대표한다.**
        """
        if not self.won_per_kg_avg:
            return False
        return abs(self.mean_raw - self.won_per_kg_avg) / self.won_per_kg_avg > 0.15

    @property
    def enough(self) -> bool:
        return self.n >= MIN_RECORDS_PER_MARKET

    @property
    def mixed_pack(self) -> bool:
        """규격이 섞여 있으면 원/kg 환산이 없을 때 비교가 왜곡된다."""
        return len(self.pack_sizes) > 1

    @property
    def typical_pack(self) -> float:
        """그 시장에서 흔한 포장 크기(kg). ### 원/kg 만으로는 못 보는 것을 보여준다."""
        return median(sorted(self.pack_sizes)) if self.pack_sizes else 0.0


@dataclass
class Coverage:
    """### 표본이 하루를 얼마나 덮나. 아래 실물이 이 칸을 만들었다.

    건수·시장 수만 세면 못 잡는 실패가 있다:
      기존 도구는 하루 129,536건 중 1,000건(0.77%)만 받아 거기서 품목을 거른다.
      그 1,000건에는 **서울가락이 아예 없다**(page 1 = 시장 6종, 안동 64.3%).
      ⇒ "1,000건"은 많아 보이지만 «전국 비교» 의 근거가 못 된다.
    ### 그래서 「몇 건 봤나」가 아니라 「하루의 몇 %를, 몇 개 시장을 봤나」를 잰다.
    """

    fetched: int  # 우리가 실제로 받은 원본 레코드 수
    day_total: int | None  # 그날 전체 (API totalCount). 모르면 None
    markets_seen: int  # 표본에 등장한 시장 수 (품목 필터 前)
    markets_nationwide: int = 33  # get_market_list 실측
    product_complete: bool = False  # ### 이 «품목» 에 대해서는 전 기록을 가졌나

    @property
    def ratio(self) -> float | None:
        if not self.day_total:
            return None
        return self.fetched / self.day_total

    @property
    def truncated(self) -> bool:
        """전량을 못 받았다 = 부재를 주장할 수 없다.

        ### 예외 하나 — «그 품목» 의 그날 기록을 전부 가졌으면 그 품목엔 못 본 시장이 없다.
        하루 전체의 일부만 받았어도 **그 품목 비교는 성립한다.**
        (데모 추출본이 이 경우다. 그 사실을 파일이 스스로 밝히고, 목록 밖 품목엔 안 준다.)
        """
        if self.product_complete:
            return False
        return self.day_total is not None and self.fetched < self.day_total

    @property
    def market_ratio(self) -> float:
        return self.markets_seen / self.markets_nationwide if self.markets_nationwide else 0.0

    def warnings(self) -> list[str]:
        out = []
        if self.product_complete:
            out.append(
                f"하루 전체 {self.day_total:,}건 중 일부만 받았으나 "
                "이 품목의 그날 기록은 전부 들어 있다 — 그래서 이 품목 비교는 성립한다"
                if self.day_total
                else "이 품목의 그날 기록은 전부 들어 있다"
            )
        elif self.day_total is None:
            out.append("그날 전체 건수를 모른다 — 이 표본이 하루를 얼마나 덮는지 판정 불가")
        elif self.truncated:
            out.append(
                f"하루 {self.day_total:,}건 중 {self.fetched:,}건({self.ratio*100:.2f}%)만 봤다 "
                "— 여기 없는 시장은 '없는' 것이 아니라 '못 본' 것이다"
            )
        if self.markets_seen and self.markets_seen < self.markets_nationwide:
            out.append(
                f"표본에 시장이 {self.markets_seen}/{self.markets_nationwide}곳만 들어왔다"
            )
        return out


@dataclass
class Evidence:
    product: str
    date: str
    markets: list[MarketStat]
    n_total: int
    n_dropped_total: int
    coverage: Coverage | None = None

    # ─── 판정 ───
    @property
    def usable_markets(self) -> list[MarketStat]:
        return [m for m in self.markets if m.enough]

    @property
    def sufficient(self) -> bool:
        """### 절단된 표본으로는 「전국 비교」를 주장하지 않는다.

        건수가 아무리 많아도, 하루의 일부만 본 표본에서 「어느 시장이 가장 비싸다」는
        말할 수 없다. 못 본 시장이 더 비쌀 수 있고 우리는 그것을 배제하지 못한다.
        """
        if self.coverage and self.coverage.truncated:
            return False
        return (
            len(self.usable_markets) >= MIN_MARKETS
            and self.n_total >= MIN_TOTAL_RECORDS
        )

    def why_insufficient(self) -> list[str]:
        """왜 못 답하는지 «구체적으로». 「데이터 부족」 한 마디로 끝내지 않는다."""
        if self.sufficient:
            return []
        out = []
        if self.coverage and self.coverage.truncated:
            c = self.coverage
            out.append(
                f"표본이 하루의 {c.ratio*100:.2f}%({c.fetched:,}/{c.day_total:,})뿐이라 "
                "시장 비교를 할 수 없다 — 못 본 시장이 더 비쌀 수 있고 그것을 배제하지 못한다"
            )
        if not self.markets:
            # ### 「전국에서 0건」과 「이 표본에 0건」은 다르다. 절단된 표본에서 앞엣말을 하면
            #   그게 정확히 우리가 잡으려는 그 혼동이다(못 본 것을 없는 것이라 부르기).
            if self.coverage and self.coverage.truncated:
                out.append(
                    f"'{self.product}' 가 이 표본 안에는 0건이다 "
                    "— 그날 전국에 없었다는 뜻이 아니라 우리가 못 봤다는 뜻이다"
                )
            else:
                out.append(f"{self.date}에 '{self.product}' 경매 기록이 전국에서 0건이다")
            return out
        u = len(self.usable_markets)
        if u < MIN_MARKETS:
            thin = [f"{m.market}({m.n}건)" for m in self.markets if not m.enough]
            out.append(
                f"비교하려면 {MIN_RECORDS_PER_MARKET}건 이상인 시장이 {MIN_MARKETS}곳 필요한데 "
                f"{u}곳뿐이다"
                + (f" — 건수가 모자란 곳: {', '.join(thin)}" if thin else "")
            )
        if self.n_total < MIN_TOTAL_RECORDS:
            out.append(f"전체 {self.n_total}건으로 최소 {MIN_TOTAL_RECORDS}건에 못 미친다")
        return out

    def caveats(self) -> list[str]:
        """답을 하더라도 «함께 말해야 하는 것». 숨기면 우리 답이 아니다.

        ### 다만 «전부 나열» 하지 않는다 — 실측상 한 턴 소요의 89% 가 «최종 답 생성» 이고 출력 길이와 붙어 있다.
        시장 32곳에 규격 섞임을 한 줄씩 쓰면 28줄이 된다(실제로 그랬다).
        ⇒ **같은 종류는 세어서 한 줄로.** 정보를 빼는 게 아니라 뭉친다.
        """
        out = []
        if self.coverage:
            out += self.coverage.warnings()
        if self.n_dropped_total:
            out.append(
                f"단위중량이 없어 원/kg 환산을 못 한 {self.n_dropped_total}건은 계산에서 뺐다"
            )
        mixed = [m for m in self.usable_markets if m.mixed_pack]
        if mixed:
            out.append(
                f"{len(mixed)}개 시장이 포장 규격이 섞여 있어 전부 원/kg 로 맞춰 비교했다"
                f" (예: {mixed[0].market} "
                f"{', '.join(f'{s:g}kg' for s in sorted(mixed[0].pack_sizes)[:4])})"
            )
        # ### 원/kg 를 맞춰도 «같은 것을 비교한다» 는 보장이 아니다.
        #   실물(2026-08-28 배추): 춘천 = 1kg 비닐봉지 37,000원/kg ↔ 안산 = 12kg 상자 250원/kg.
        #   둘 다 진짜 낙찰이고 둘 다 «배추» 다. 그런데 ### 소매 소포장과 대량 도매다.
        #   ⇒ 격차가 5,500% 로 나왔다. 그건 «어느 시장이 후하다» 가 아니라 «다른 장사» 다.
        u = self.usable_markets
        if len(u) >= 2:
            top_p, bot_p = u[0].typical_pack, u[-1].typical_pack
            if top_p and bot_p and max(top_p, bot_p) / min(top_p, bot_p) >= 4:
                out.append(
                    f"⚠️ 포장 급이 다르다 — {u[0].market}는 {top_p:g}kg, {u[-1].market}는 {bot_p:g}kg. "
                    "소포장과 대량 도매를 맞대면 원/kg 격차는 커진다. "
                    "출하 물량과 포장이 비슷한 시장끼리 비교할 것"
                )
        skewed = [m for m in self.usable_markets if m.skewed]
        if skewed:
            names = ", ".join(m.market for m in skewed[:3])
            more = f" 외 {len(skewed)-3}곳" if len(skewed) > 3 else ""
            out.append(
                f"{names}{more}은 한두 건이 값을 크게 끌고 있어 중앙값으로 대표했다"
            )
        return out


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def build_evidence(
    items: list[dict],
    product: str,
    date: str,
    day_total: int | None = None,
    all_day_items: list[dict] | None = None,
    product_complete: bool = False,
) -> Evidence:
    """data.go.kr 원본 레코드 목록 → 근거 묶음.

    items        = 품목으로 «거른 뒤» 의 레코드
    day_total    = 그날 전체 건수(API totalCount). 없으면 덮음률 판정 불가로 표시
    all_day_items= 거르기 «전» 의 표본. 표본이 몇 개 시장을 담았는지 세는 데 쓴다
    """
    by_market: dict[str, dict] = {}
    dropped_total = 0

    for it in items:
        market = (it.get("whsl_mrkt_nm") or "").strip()
        price = _num(it.get("scsbd_prc"))
        unit_qty = _num(it.get("unit_qty"))
        if not market or price <= 0:
            continue

        slot = by_market.setdefault(
            market,
            {"pk": [], "dropped": 0, "qty": 0.0, "packs": set(), "vars": set()},
        )
        slot["qty"] += _num(it.get("qty"))
        v = (it.get("gds_sclsf_nm") or "").strip()
        if v:
            slot["vars"].add(v)

        # ★ 여기가 핵심 — 단위중량이 없으면 «환산 불가» 로 따로 센다. 0 으로 안 채운다.
        if unit_qty <= 0:
            slot["dropped"] += 1
            dropped_total += 1
            continue
        slot["packs"].add(unit_qty)
        slot["pk"].append(price / unit_qty)

    stats: list[MarketStat] = []
    for market, s in by_market.items():
        pk = s["pk"]
        if not pk:
            stats.append(
                MarketStat(market, 0, s["dropped"], 0.0, 0.0, 0.0, s["qty"], s["packs"], s["vars"])
            )
            continue
        stats.append(
            MarketStat(
                market=market,
                n=len(pk),
                n_dropped=s["dropped"],
                won_per_kg_avg=median(pk),  # ### 중앙값. 이유 = MarketStat.skewed 주석
                won_per_kg_min=min(pk),
                won_per_kg_max=max(pk),
                total_qty=s["qty"],
                pack_sizes=s["packs"],
                varieties=s["vars"],
                mean_raw=sum(pk) / len(pk),
            )
        )

    stats.sort(key=lambda m: -m.won_per_kg_avg)  # 출하자는 비싼 곳이 궁금하다

    sample = all_day_items if all_day_items is not None else items
    cov = Coverage(
        fetched=len(sample),
        day_total=day_total,
        markets_seen=len({(it.get("whsl_mrkt_nm") or "").strip() for it in sample} - {""}),
        product_complete=product_complete,
    )
    return Evidence(
        product=product,
        date=date,
        markets=stats,
        n_total=sum(m.n for m in stats),
        n_dropped_total=dropped_total,
        coverage=cov,
    )


def _why_short(ev: Evidence) -> str:
    """거절 사유를 «한 낱말 수준» 으로. ### 숫자를 넣지 않는다 — 모델이 그걸로 표를 만든다."""
    c = ev.coverage
    if c and c.truncated:
        if not ev.markets:
            return "이 표본 안에 없다 (그날 없었다는 뜻이 아니다)"
        return "하루의 일부만 봐서 시장 비교가 성립하지 않는다"
    if not ev.markets:
        return "그날 전국 경매 기록이 없다"
    if len(ev.usable_markets) < MIN_MARKETS:
        return "비교할 만큼의 시장이 안 된다"
    return "근거가 모자라다"


def render(ev: Evidence, top_n: int = 5) -> str:
    """에이전트가 그대로 읽을 텍스트. ### 답이든 «모른다» 든 근거 수를 항상 함께 낸다.

    top_n = 전부 나열하지 않는다. 32곳을 다 쓰면 79줄이 되고(실측) 그 길이가 그대로 비용이다.
    """
    head = f"[근거] '{ev.product}' / {ev.date}"

    if not ev.sufficient:
        # ### 맨 앞에 «그대로 옮길 한 줄» 을 준다.
        #   실측: 모델이 판정을 자기 말로 다시 쓰면 길어지고(소요의 89%가 생성)
        #   ### 「모른다」 경로에서 특히 나빠진다 — 숫자 앵커가 없어 문장이 흐트러진다
        #   (베트남어·한자가 섞여 나왔다). ⇒ 옮길 문장을 우리가 만들어 준다.
        why = ev.why_insufficient()
        # 🔴 **베낄 줄에 숫자를 넣지 마라** (2026-08-30 실측).
        #    처음엔 여기 이유 전문을 넣었다: *"…표본이 하루의 34.97%(45,301/129,536)뿐이라…"*
        #    ### 모델이 그 숫자들로 «없는 날짜별 건수 표» 를 만들어 냈다
        #    (*"2026-08-27 양파: 101,219건 확보"* — 그런 조회를 한 적이 없다).
        #    ⇒ ### **한 줄은 「짧고 숫자 없이」.** 자세한 이유는 아래 본문에 그대로 둔다.
        #    = 거절 화면에서 가격을 뺀 것과 같은 이유다. 유혹을 안 만든다.
        lines = [
            f"[한 줄] {ev.date} {ev.product}: 답할 수 없다 — {_why_short(ev)}.",
            "",
            f"{head} — 판정: 근거 부족. 어느 시장이 유리한지 말할 수 없다.",
            "",
            "왜:",
        ]
        lines += [f"  - {r}" for r in ev.why_insufficient()]
        if ev.markets:
            # 🔴 **여기에 가격을 「참고용」 이라 달아서 보여줬다. 모델이 그냥 썼다** (2026-08-30 실측 4/6).
            #    ### 라벨로 «쓰지 마라» 부탁하는 것은 프롬프트로 조심하라는 것과 같다.
            #    ⇒ **안 보여준다.** 비교를 못 하겠다고 해놓고 비교할 재료를 내놓지 않는다.
            #    남기는 것 = 시장 «이름과 건수» — 다음 질문을 좁히는 데 쓰이고, 답으로 오독될 수 없다.
            seen = ", ".join(f"{m.market}({m.n}건)" for m in ev.markets[:6])
            more = f" 외 {len(ev.markets) - 6}곳" if len(ev.markets) > 6 else ""
            lines += [
                "",
                f"표본에 있던 시장: {seen}{more}",
                "### 가격은 일부러 싣지 않는다 — 비교가 성립하지 않는 표본의 값이라 인용되면 안 된다.",
            ]
        lines += ["", "권함: 다른 날짜로 다시 보거나, 최근 며칠 추세로 판단할 것."]
        return "\n".join(lines)

    u = ev.usable_markets
    _t = u[0]
    lines = [
        f"[한 줄] {ev.date} {ev.product}: {_t.market}가 가장 높다 — "
        f"{_t.won_per_kg_avg:,.0f}원/kg(중앙값), 근거 {_t.n:,}건, "
        f"{_t.typical_pack:g}kg 포장 기준.",
        "",
        f"{head} — 판정: 비교 가능 ({len(u)}개 시장 / 총 {ev.n_total:,}건)",
        "",
    ]
    for i, m in enumerate(u[:top_n], 1):
        lines.append(
            f"  {i}. {m.market}: {m.won_per_kg_avg:,.0f}원/kg "
            f"(중앙값 · 근거 {m.n:,}건 · 흔한 포장 {m.typical_pack:g}kg · 물량 {m.total_qty:,.0f})"
        )
    if len(u) > top_n:
        bottom = u[-1]
        lines.append(f"  … 중간 {len(u) - top_n - 1}곳 생략")
        lines.append(
            f"  {len(u)}. {bottom.market}: {bottom.won_per_kg_avg:,.0f}원/kg "
            f"(가장 낮음 · 근거 {bottom.n:,}건 · 흔한 포장 {bottom.typical_pack:g}kg)"
        )
    top, bottom = u[0], u[-1]
    gap = top.won_per_kg_avg - bottom.won_per_kg_avg
    pct = (gap / bottom.won_per_kg_avg * 100) if bottom.won_per_kg_avg else 0
    lines += [
        "",
        f"  1위 {top.market} 와 최하위 {bottom.market} 차이: {gap:,.0f}원/kg ({pct:.0f}%)",
    ]
    cv = ev.caveats()
    if cv:
        lines += ["", "함께 봐야 할 것:"] + [f"  - {c}" for c in cv]
    return "\n".join(lines)
