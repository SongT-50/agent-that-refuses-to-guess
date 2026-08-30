"""장면3(못 봤다 경로)에서 모델이 없는 수치를 만드나. 6회."""
import logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import build_agent, _leaked
Q = "2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?"
BIG = re.compile(r"\d{3,}|\d[\d,.]*%")   # 3자리 이상 수 또는 퍼센트
N = 6
bad = 0
for i in range(N):
    out = ""
    for _ in range(3):
        out = str(build_agent()(Q))
        if not _leaked(out): break
    hits = BIG.findall(out)
    # 날짜(2026, 08, 28)는 정상
    hits = [h for h in hits if h not in ("2026",) and not h.startswith("2026")]
    if hits: bad += 1
    print(f"  {i+1}. {'🔴 ' + str(hits[:4]) if hits else '  깨끗'} | {out[:80]}")
print(f"\n지어낸 수치가 섞인 회차: {bad}/{N}")
