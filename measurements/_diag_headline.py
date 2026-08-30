"""[한 줄] 도입이 출력 품질을 실제로 바꾸나. 두 경로 각 6회."""
import logging, os, re, sys, statistics
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import build_agent, _leaked
# 한자 + 가나 + 키릴 + 라틴(로마자 낱말) + 태국 + 베트남 성조
FOREIGN = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF\u0E00-\u0E7F]|[A-Za-z]{2,}")
CASES = [("충분(8/28 복숭아)", "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"),
         ("불충분(8/30 배추)", "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?")]
N = 6
for tag, q in CASES:
    bad = 0; lens = []
    for i in range(N):
        out = ""
        for _ in range(3):
            out = str(build_agent()(q))
            if not _leaked(out): break
        hits = sorted(set(FOREIGN.findall(out)))
        # kg 는 정상 단위라 제외
        hits = [h for h in hits if h.lower() not in ("kg",)]
        lens.append(len(out))
        if hits: bad += 1
        print(f"  {tag} {i+1}. {'🔴 ' + ''.join(hits[:4]) if hits else '  깨끗'} | {len(out):3d}자 | {out[:70]}")
    print(f"[{tag}] 외래 혼입 {bad}/{N} · 길이 중앙 {statistics.median(lens):.0f}자\n")
