"""거절 경로에서 모델이 «없는 시장·가격» 을 지어내나. 도구 수정 후 6회씩."""
import logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import build_agent, _leaked
from data import load_day  # 33개 실존 시장 확보용
REAL = set()
for x in load_day("2026-08-28").items:
    n = (x.get("whsl_mrkt_nm") or "").strip()
    if n: REAL.add(n)
MKT = re.compile(r"([가-힣]{2,5})\s*(?:시장|시)")
PRICE = re.compile(r"[\d,]{2,}\s*(?:원|달러)")
CASES = [("0건 (8/30 배추)", "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?"),
         ("절단 (8/26 배추)", "2026-08-26에 배추를 출하하려는데 어느 시장이 유리해?")]
N = 6
for tag, q in CASES:
    fake_mkt = 0; had_price = 0
    for i in range(N):
        out = ""
        for _ in range(3):
            out = str(build_agent()(q))
            if not _leaked(out): break
        names = {m for m in MKT.findall(out)}
        invented = {n for n in names if n not in REAL and not any(n in r or r in n for r in REAL)}
        prices = PRICE.findall(out)
        if invented: fake_mkt += 1
        if prices: had_price += 1
        flag = "🔴" if (invented or prices) else "  "
        print(f"  {tag} {i+1}. {flag} 지어낸시장{sorted(invented) or '없음'} 가격{prices or '없음'} | {out[:75]}")
    print(f"[{tag}] 없는 시장 언급 {fake_mkt}/{N} · 가격 언급 {had_price}/{N}\n")
print("⚠️ 거절 경로에서 가격이 나오면 그 자체가 오류다. 도구가 가격을 안 줬다.")
