"""도구 누수 - 조건마다 6회씩. n=1 로 원인을 정하지 않는다."""
import logging, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strands import Agent
from strands.models.ollama import OllamaModel
from tools import ALL_TOOLS, SYSTEM_PROMPT

KO = """당신은 한국 농산물 도매시장 출하 상담자다.
규칙:
1. 도구가 돌려준 표와 수치를 다시 타이핑하지 마라.
2. 당신의 답은 두 문장 이내다.
3. 도구가 근거 부족이라 하면 절대 추천하지 마라.
4. 도구에 없는 시장·가격을 지어내지 마라.
"""
Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"
N = 6

def once(prompt, tools):
    m = OllamaModel(host="http://localhost:11434", model_id="llama3.2:3b")
    a = Agent(model=m, tools=tools, system_prompt=prompt, callback_handler=None)
    try: out = str(a(Q))
    except Exception as e: return False, f"ERR {type(e).__name__}"
    used = any("toolUse" in c for msg in a.messages for c in (msg.get("content") or []) if isinstance(c, dict))
    leaked = '"name"' in out and 'parameters' in out
    return (used and not leaked), out[:60]

for tag, prompt in (("영어(현행)", SYSTEM_PROMPT), ("한국어", KO)):
    ok = 0; notes=[]
    t0=time.time()
    for i in range(N):
        good, s = once(prompt, ALL_TOOLS)
        ok += good; notes.append("O" if good else "X")
    print(f"[{tag}] 성공 {ok}/{N}  {''.join(notes)}   ({time.time()-t0:.0f}초)")
