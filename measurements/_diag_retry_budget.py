"""
촬영 부담 실측 — **재시도가 «소진»되는 회차가 얼마나 되나**

MANUS 판단: 재시도 뒤 답이 나오면 남기고, ### 소진돼 답을 못 내면 다시 찍는다.
⇒ 소진율이 촬영 재시도 횟수를 정한다. 그걸 안 재고 «가끔 뜬다» 로 두면 MANUS 가 몇 번을
   찍어야 하는지 모른다.

장면 셋 × N회. 각 회차의 «시도 횟수» 와 «끝내 실패했나» 를 센다.
"""
import io, contextlib, logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent as A

A._pin_demo_cache()
CASES = [("장면1", "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"),
         ("장면2", "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?"),
         ("장면3", "2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?")]
N = 5
rows = []
for tag, q in CASES:
    for i in range(N):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            A.ask(q)
        s = buf.getvalue()
        retries = len(re.findall(r"재시도 \d/\d", s))
        failed = "답을 내지 않는다" in s or "근거가 없어 답을 내지 않는다" in s
        rows.append((tag, retries, failed))
        print(f"  {tag} {i+1}. 시도 {retries+1}회 {'🔴 소진' if failed else '✅ 답 나옴'}")

n = len(rows)
exhausted = sum(1 for _,_,f in rows if f)
first_try = sum(1 for _,r,f in rows if r == 0 and not f)
print(f"\n{'='*60}")
print(f"  전체 {n}회 · 첫 시도 성공 {first_try} · 재시도 후 성공 {n-first_try-exhausted} · 소진 {exhausted}")
if exhausted:
    print(f"  ### 소진율 {exhausted/n*100:.0f}% — 촬영 중 {n//max(exhausted,1)}회에 한 번쯤 다시 찍어야 한다")
else:
    print(f"  ### 소진 0건 — 이 표본에선 다시 찍을 일이 없었다. ⚠️ n={n} 이다. 0을 「안 난다」로 읽지 마라")
