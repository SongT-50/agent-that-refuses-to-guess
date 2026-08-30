"""
209초가 «재시도 예산» 탓인가 «기계» 탓인가 — 같은 조건에서 예산만 바꿔 가른다

내가 MANUS 에게 «원인을 못 갈랐다» 고 적었다. 추론으로 닫지 않는다.
같은 세션·같은 순서로 retries=2 와 retries=5 를 번갈아 돌린다(경합이 있으면 둘 다 느려진다).

가르는 방법:
  · 둘 다 느리다        -> 기계 경합. 예산은 무관
  · 5 만 느리고 2 는 «빠른 대신 실패» -> ### 예산이 실패를 시간으로 바꾼 것. 회귀가 아니라 교환
  · 5 만 느리고 2 는 «빠르고 성공»    -> 예산이 순수 손해. 되돌려야 한다
"""
import io, contextlib, logging, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent as A

A._pin_demo_cache()
Q = A.DEMO[0]  # 가장 무거웠던 장면
PAIRS = 3
rows = []
for i in range(PAIRS):
    for budget in (2, 5):
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            A.ask(Q, retries=budget)
        s = buf.getvalue()
        dt = time.time() - t0
        r = len(re.findall(r"재시도 \d/\d", s))
        failed = "답을 내지 않는다" in s
        rows.append((budget, dt, r, failed))
        print(f"  예산{budget}  {dt:6.1f}초 · 시도 {r+1}회 {'🔴 실패' if failed else '✅ 성공'}")

def summ(b):
    xs = [(d, r, f) for bb, d, r, f in rows if bb == b]
    t = [d for d, _, _ in xs]
    return f"예산{b}: 평균 {sum(t)/len(t):5.1f}초 · 최대 {max(t):5.1f}초 · 실패 {sum(1 for *_ ,f in xs if f)}/{len(xs)}"

print(f"\n{'='*62}")
print("  " + summ(2))
print("  " + summ(5))
print(f"{'='*62}")
t2 = [d for b, d, _, _ in rows if b == 2]
t5 = [d for b, d, _, _ in rows if b == 5]
f2 = sum(1 for b, _, _, f in rows if b == 2 and f)
f5 = sum(1 for b, _, _, f in rows if b == 5 and f)
if max(t2) > 60 and max(t5) > 60:
    print("  ⇒ 둘 다 느린 구간이 있다 = 기계 쪽 요인이 있다")
if f2 > f5:
    print("  ⇒ 예산2 가 더 자주 실패한다 = 예산5 는 «실패를 시간으로 바꾼 것». 교환이지 회귀가 아니다")
if f2 == f5 == 0 and sum(t5)/len(t5) > sum(t2)/len(t2) * 1.5:
    print("  ⇒ 실패는 같은데 예산5 만 느리다 = 순수 손해. 되돌려라")
print(f"  ⚠️ n={PAIRS} 쌍이다. 이 표본으로 «확정» 하지 마라")
