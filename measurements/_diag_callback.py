"""agent.py 만 계속 실패한다. 남은 차이 = callback_handler. 6회씩 가른다."""
import logging, os, sys, io, contextlib
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strands import Agent
from strands.models.ollama import OllamaModel
from tools import ALL_TOOLS, SYSTEM_PROMPT
Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"
N = 6

def once(use_default_handler):
    m = OllamaModel(host="http://localhost:11434", model_id="llama3.2:3b")
    kw = {} if use_default_handler else {"callback_handler": None}
    a = Agent(model=m, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT, **kw)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            out = str(a(Q))
    except Exception as e:
        return False
    used = any("toolUse" in c for msg in a.messages for c in (msg.get("content") or []) if isinstance(c, dict))
    leaked = '"name"' in out and 'parameters' in out
    return used and not leaked

for tag, dflt in (("기본 handler (agent.py 와 같음)", True), ("handler=None (진단들과 같음)", False)):
    r = [once(dflt) for _ in range(N)]
    print(f"[{tag}] 성공 {sum(r)}/{N}  {''.join('O' if x else 'X' for x in r)}")
