"""도구 호출이 왜 텍스트로 새나 - 조건을 하나씩 바꿔 가른다."""
import logging, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strands import Agent
from strands.models.ollama import OllamaModel
from tools import ALL_TOOLS, SYSTEM_PROMPT

EN = ("You are a Korean wholesale market shipping advisor.\n"
      "Rules:\n"
      "1. Do NOT retype tables or numbers from tool output.\n"
      "2. Answer in at most 2 sentences, in Korean.\n"
      "3. If the tool says evidence is insufficient, do NOT recommend anything.\n"
      "4. Never invent markets or prices.\n")
SHORT_EN = "You are a shipping advisor. Use tools. Answer in Korean, 2 sentences max."

Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"

def run(tag, prompt, tools):
    m = OllamaModel(host="http://localhost:11434", model_id="llama3.2:3b")
    a = Agent(model=m, tools=tools, system_prompt=prompt, callback_handler=None)
    t0=time.time()
    try: out = str(a(Q))
    except Exception as e: out = f"<ERR {type(e).__name__}: {e}>"
    used=[]
    for msg in a.messages:
        for c in msg.get("content",[]) or []:
            if isinstance(c,dict) and "toolUse" in c: used.append(c["toolUse"].get("name"))
    leaked = '"name"' in out and '"parameters' in out
    print(f"\n[{tag}] {time.time()-t0:.1f}초")
    print(f"   도구 실행: {used or '없음'}   |   텍스트로 샜나: {'🔴 예' if leaked else '아니오'}")
    print(f"   답: {out[:150]}")
    return bool(used) and not leaked

print("="*70); print("도구 호출 누수 진단"); print("="*70)
r1 = run("A 한국어 프롬프트(현행)", SYSTEM_PROMPT, ALL_TOOLS)
r2 = run("B 영어 프롬프트", EN, ALL_TOOLS)
r3 = run("C 영어 짧은 프롬프트", SHORT_EN, ALL_TOOLS)
r4 = run("D 영어 + 도구 1개", SHORT_EN, ALL_TOOLS[:1])
print("\n" + "="*70)
print(f"판정: A={r1} B={r2} C={r3} D={r4}")
print("  A만 실패면 -> 한국어 프롬프트가 원인")
print("  전부 실패면 -> 이 도구 정의 자체 또는 3B 한계")
