"""한국어 출력에 다른 문자가 섞이나. 6회 센다."""
import logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import build_agent, _leaked
Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"
# 한중일 한자 + 베트남어 성조문자 + 태국/키릴 등
FOREIGN = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF"
                     r"\u00C0-\u01FF\u1EA0-\u1EF9\u0E00-\u0E7F]")
N = 6
bad = 0
for i in range(1, N+1):
    out = ""
    for _ in range(3):
        out = str(build_agent()(Q))
        if not _leaked(out): break
    hits = sorted(set(FOREIGN.findall(out)))
    if hits: bad += 1
    print(f"{i}. {'🔴' if hits else '  '} {''.join(hits) if hits else '깨끗'}  | {out[:70]}")
print(f"\n외래 문자가 섞인 회차: {bad}/{N}")
print("⚠️ 한 질문으로만 쟀다. 그리고 «섞였다» 는 «틀렸다» 와 다르다 - 수치 정확성은 따로다.")
