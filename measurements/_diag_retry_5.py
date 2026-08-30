"""재시도 예산을 2 -> 5 로 올리면 소진율이 줄나. 같은 15회."""
import io, contextlib, logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent as A
A._pin_demo_cache()
CASES = [("장면1","2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"),
         ("장면2","2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?"),
         ("장면3","2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?")]
N=5; rows=[]
for tag,q in CASES:
    for i in range(N):
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf): A.ask(q, retries=5)
        s=buf.getvalue()
        r=len(re.findall(r"재시도 \d/\d", s)); f="답을 내지 않는다" in s
        rows.append((tag,r,f))
        print(f"  {tag} {i+1}. 시도 {r+1}회 {'🔴 소진' if f else '✅'}")
n=len(rows); ex=sum(1 for _,_,f in rows if f)
tries=[r+1 for _,r,f in rows]
print(f"\n전체 {n}회 · 소진 {ex} ({ex/n*100:.0f}%) · 시도 중앙 {sorted(tries)[n//2]}회 · 최대 {max(tries)}회")
