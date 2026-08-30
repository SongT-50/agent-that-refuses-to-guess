"""세 장면이 «몇 번에 한 번» 제대로 나오나. 각 4회."""
import io, logging, os, re, sys, contextlib
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent as A
FOREIGN = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF]|\b(gi[aá]|trung|b[ìi]nh|x[aá]c)\b", re.I)
CASES = [("장면1 답한다", "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?", "가장 높다"),
         ("장면2 전국 0건", "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?", "전국 경매 기록이 없다"),
         ("장면3 못 봤다", "2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?", "이 표본 안에 없다")]
N = 4
for tag, q, expect in CASES:
    ok = 0; dirty = 0
    for i in range(N):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            A.ask(q)
        s = buf.getvalue()
        # 답 줄만 본다 (재시도 로그 제외)
        ans = [ln for ln in s.splitlines() if ln.strip() and not ln.strip().startswith(("[", "─", "질문:", "  ["))]
        body = " ".join(ans)
        good = expect in body
        f = FOREIGN.findall(body)
        ok += good; dirty += bool(f)
        print(f"  {tag} {i+1}. {'✅' if good else '🔴'} {'외래어' + str(f[:2]) if f else '깨끗'} | {body[:70]}")
    print(f"[{tag}] 기대한 답 {ok}/{N} · 외래어 혼입 {dirty}/{N}\n")
