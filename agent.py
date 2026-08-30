"""
출하자 판단 에이전트 — Strands 배선

돌리기:
    ../.venv/Scripts/python.exe agent.py                 # 데모 두 장면
    ../.venv/Scripts/python.exe agent.py "배추 어디에 낼까"  # 한 번만

### 이 파일은 «배선» 이다. 판정은 evidence.py 가 하고 데이터는 data.py 가 한다.
   모델은 도구를 고르고 결론을 두 문장으로 전한다. 그게 전부다.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 🔴 W-44: MCP·httpx 가 요청 URL 을 INFO 로 찍고 거기 API 키가 들어 있다.
#    데모 영상·공개 저장소에 그대로 나가면 키가 노출된다.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strands import Agent  # noqa: E402
from strands.models.ollama import OllamaModel  # noqa: E402

from tools import ALL_TOOLS, SYSTEM_PROMPT  # noqa: E402

MODEL_ID = os.getenv("SHIPPER_MODEL", "llama3.2:3b")
OLLAMA = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def build_agent() -> Agent:
    """### 모델을 «명시» 한다. 안 하면 Strands 기본값이 유료 Bedrock 이다.

    🔴 `callback_handler=None` 도 «명시» 다. 기본 스트리밍 핸들러를 쓰면
    작은 모델이 tool-call 을 «텍스트로» 뱉는 일이 잦다 — 실측(n=6):
        기본 handler   성공 **2/6**
        handler=None   성공 **5/6**
    ⇒ 스트리밍 출력을 잃는 대신 도구가 실제로 돈다. 데모에는 후자가 필요하다.
    """
    return Agent(
        model=OllamaModel(host=OLLAMA, model_id=MODEL_ID),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def _leaked(text: str) -> bool:
    """모델이 도구를 «부르지 않고» 호출 JSON 을 글자로 뱉었나.

    ### handler 를 고쳐도 6회 중 1회는 여전히 샌다. 그 1회를 «희망» 으로 두지 않는다.
    구조로 잡는다 — 감지하고 다시 시킨다.
    """
    t = text.strip()
    return '"name"' in t and "parameters" in t and t.startswith("{")


def _tool_headline(agent: Agent) -> str | None:
    """도구가 돌려준 `[한 줄]` 을 그대로 꺼낸다.

    🔴 **왜 모델이 쓴 문장을 안 쓰나** (2026-08-30 실측 n=6):
       도구는 깨끗한 한국어를 준다. 그런데 모델이 «다시 쓰면서» 망가뜨린다 —
       `giá` · `trung` · `bình` · `值` · `원子` 가 **6회 중 4회 이상** 섞였고,
       한 번은 ### **물량 1,648 을 「1,648건」이라 라벨을 갈아 붙였다.**
    ### ⇒ 판정도 문장도 코드가 만든다. 모델은 «어떤 도구를 부를지» 를 고른다.
       그게 이 프로젝트가 처음부터 말한 것이다 — *"판정은 코드에 둔다."*
    ⚠️ 모델 문장을 버리지는 않는다. 아래에 함께 보여주고, **권위는 도구 줄에 둔다.**
    """
    # 🔴 **어느 도구의 답인지 확인한다** (2026-08-30, 내가 만든 버그를 고친 것):
    #    처음엔 «마지막 [한 줄]» 을 그냥 집었다. 그런데 모델이 누수 재시도 끝에
    #    ### `available_dates` 를 부른 회차가 있었고, 코드가 그 헤드라인
    #    («비교 가능: 2026-08-28»)을 ### **「어느 시장이 유리한가」의 답인 양 출력했다.**
    #    ⇒ 도구를 코드로 고른 게 아니라 **모델이 고른 것을 코드가 권위 있게 포장**한 셈이다.
    #    ### 전보다 나쁘다 — 틀린 답에 확신을 입혔다.
    want = "shipping_market_advice"
    use_ids = {
        c["toolUse"]["toolUseId"]
        for m in agent.messages
        for c in (m.get("content") or [])
        if isinstance(c, dict) and c.get("toolUse", {}).get("name") == want
    }
    for msg in reversed(agent.messages):
        for c in msg.get("content", []) or []:
            if not isinstance(c, dict):
                continue
            res = c.get("toolResult")
            if not res or res.get("toolUseId") not in use_ids:
                continue
            for part in res.get("content", []) or []:
                text = part.get("text") if isinstance(part, dict) else None
                if not text:
                    continue
                for line in text.splitlines():
                    if line.startswith("[한 줄]"):
                        return line[len("[한 줄]") :].strip()
    return None


def ask(q: str, retries: int = 5) -> None:
    """### 재시도는 «새 에이전트» 로 한다.

    🔴 **예산이 2였다. 재서 5로 올렸다** (2026-08-30, 각 15회):
        retries=2 → 소진 **2/15 (13%)** · retries=5 → 소진 **0/15**
        ### **중앙 시도 횟수는 둘 다 1회다** — 평소엔 안 느려지고 나쁜 회차만 더 버틴다.
    ### 왜 중요한가: 소진되면 답을 «안 낸다». 그건 옳은 동작이지만 데모 화면에선
    「안 도는 것」으로 읽힌다(심사 5번이 end-to-end 를 본다).
    ⚠️ 최대 6회까지 간 회차가 있었다. 그때는 그만큼 느리다. **숨기지 않는다.**

    ⚠️ 처음엔 `agent.messages.clear()` 로 되돌리려 했다가 실패했다 —
    `EventLoopException: unsupported operand type(s) for +: NoneType and NoneType`.
    대화만 비우면 내부 상태가 안 맞는다. **샌 턴은 버리고 처음부터 만든다.**
    """
    print("\n" + "─" * 68)
    print(f"질문: {q}")
    print("─" * 68)
    t0 = time.time()
    out = ""
    headline = None
    for attempt in range(retries + 1):
        agent = build_agent()
        try:
            out = str(agent(q))
        except Exception as e:
            out = f"<ERR {type(e).__name__}: {e}>"
            break
        headline = _tool_headline(agent)
        if headline and not _leaked(out):
            break
        # ### 재시도 사유가 둘이다. 둘 다 «근거 없는 답» 으로 끝난다.
        #   ⓐ 도구 호출이 텍스트로 샜다
        #   ⓑ ### 모델이 «다른 도구» 를 불렀다 — 실측에서 `available_dates` 를 부르고
        #      날짜 목록을 「어느 시장이 유리한가」의 답인 양 내놓은 회차가 있었다.
        why = "도구 호출이 텍스트로 샜다" if _leaked(out) else "이 질문에 맞는 도구를 안 불렀다"
        if attempt < retries:
            print(f"  [{why} — 새 세션으로 재시도 {attempt + 1}/{retries}]")
    dt = time.time() - t0

    if headline:
        # ### 답은 이 줄이다. 코드가 만들었고 모델을 안 거쳤다.
        print(f"\n{headline}")
        # ⚠️ 모델이 다시 쓴 문장은 «기본으로 안 보여준다» — 같은 실행에서 그 문장이
        #    「물량 1,648」을 «1,648건» 이라 갈아 붙였다. 옆에 두면 화면에서 둘이 싸운다.
        #    보고 싶으면 SHOW_MODEL_TEXT=1.
        if os.getenv("SHOW_MODEL_TEXT") and out and not _leaked(out):
            print(f"\n  (모델이 다시 쓴 것 — 참고용, 권위는 위 줄에 있다: {out.strip()[:160]})")
    elif _leaked(out):
        print("\n🔴 도구 호출이 계속 샌다. 답을 내지 않는다 — 지어내는 것보다 낫다.")
    else:
        # ### 도구를 «안 불렀거나 다른 도구를 불렀다» = 이 질문의 근거가 없다.
        print("\n🔴 이 질문에 답할 도구가 실행되지 않았다. 근거가 없어 답을 내지 않는다.")
        if out and not _leaked(out):
            print(f"  (모델이 쓴 것 — 근거 없음: {out.strip()[:120]})")
    print(f"\n[{dt:.1f}초]")


# ### 세 장면이 «서로 다른 거절 이유» 를 보인다. 그 구별이 이 제품이다.
#
# 🔴 **장면 3 은 자료 상태에 따라 달라진다. 그래서 이 데모는 「데모 자료만」으로 돈다** —
#    MANUS 가 저장소에서 돌렸더니 장면 3 이 «답» 을 냈다(*"춘천 1,347원/kg"*).
#    ### 둘 다 옳은 동작이다. 그 기계엔 «전량 캐시» 가 있어서 양파도 완전했기 때문이다.
#    ### 그런데 나는 「데모 자료만 있는 폴더」에서 재고 «12/12» 라 보고했다.
#    = 한 조건에서 재고 특성처럼 말한 것. 오늘 이 형태를 여러 번 했다.
#    ⇒ **데모는 자기 자료를 명시한다.** 전량 캐시가 있어도 데모 추출본을 쓴다.
#      (전량으로 보고 싶으면 SHIPPER_CACHE 로 그 폴더를 가리키면 된다.)
DEMO = [
    # 장면 1 — 근거가 충분하다. 답하고, 몇 건으로 말하는지 함께 낸다.
    "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?",
    # 장면 2 — 그날 «전국에» 기록이 0건이다. 진짜로 없다.
    "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?",
    # 장면 3 — ### 「없다」가 아니라 「못 봤다」. 이게 우리가 파는 구별이다.
    #   데모 추출본은 복숭아·배추·사과·포도만 완전하다. 양파는 «못 본» 품목이다.
    "2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?",
]


def _pin_demo_cache() -> None:
    """### 데모는 「저장소가 싣는 자료」로 돈다. 사람 기계에 뭐가 있든 같은 화면이 나오게.

    안 그러면 개발자 기계(전량 캐시 있음)와 심사자 기계(데모만)가 다른 것을 보여준다.
    ⚠️ 사용자가 SHIPPER_CACHE 를 직접 지정했으면 건드리지 않는다.
    """
    if os.getenv("SHIPPER_CACHE"):
        return
    here = Path(__file__).resolve().parent / "_cache"
    demo = list(here.glob("demo-*.json.gz"))
    full = list(here.glob("[0-9]*.json"))
    if demo and full:
        pinned = here.parent / "_cache_demo_only"
        pinned.mkdir(exist_ok=True)
        for f in demo:
            target = pinned / f.name
            if not target.exists():
                target.write_bytes(f.read_bytes())
        os.environ["SHIPPER_CACHE"] = str(pinned)
        print(f"[데모 자료로 고정: {pinned.name} — 전량 캐시는 안 쓴다]")


def main() -> int:
    _pin_demo_cache()
    qs = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO
    for q in qs:
        ask(q)
    return 0


if __name__ == "__main__":
    sys.exit(main())
