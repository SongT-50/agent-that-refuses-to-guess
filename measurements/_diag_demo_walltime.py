"""
데모 전체가 «몇 초» 인가 — 촬영 예산 실측

재시도 예산을 5로 올려 소진은 0 이 됐다. 그런데 ### 나쁜 회차는 그만큼 «길어진다».
영상은 5분 제한이고 시연 말고 피치도 들어가야 한다.
⇒ MANUS 가 «시연에 몇 초를 잡아야 하나» 를 알아야 한다. 내가 경고만 하고 안 쟀다.
"""
import io, contextlib, logging, os, re, statistics, sys, time
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent as A

A._pin_demo_cache()
RUNS = 2
totals, details = [], []
for i in range(1, RUNS + 1):
    t0 = time.time()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for q in A.DEMO:
            A.ask(q)
    s = buf.getvalue()
    dt = time.time() - t0
    per = [float(x) for x in re.findall(r"\[(\d+\.\d)초\]", s)]
    retries = len(re.findall(r"재시도 \d/\d", s))
    failed = "답을 내지 않는다" in s
    totals.append(dt)
    details.append((dt, per, retries, failed))
    print(f"  {i}. 전체 {dt:5.1f}초 | 장면별 {per} | 재시도 {retries} {'🔴소진' if failed else ''}")

print(f"\n{'='*62}")
print(f"  전체 소요 (n={RUNS}) : 최소 {min(totals):.0f}초 · 중앙 {statistics.median(totals):.0f}초 · 최대 {max(totals):.0f}초")
allper = [p for _, per, _, _ in details for p in per]
print(f"  장면 하나         : 최소 {min(allper):.0f}초 · 중앙 {statistics.median(allper):.0f}초 · 최대 {max(allper):.0f}초")
print(f"  소진              : {sum(1 for *_ , f in details if f)}/{RUNS}")
print(f"\n  ⚠️ 5분(300초) 예산 대비 = 시연이 최대 {max(totals):.0f}초. 피치에 {300-max(totals):.0f}초 남는다")
print(f"  ⚠️ n={RUNS}. 최대값이 진짜 최대라는 뜻이 아니다")
