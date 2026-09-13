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
import re
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

# ### 모델 «공급자» 를 환경변수로 고른다 (2026-09-12).
#   ollama  = 로컬. 키·비용 0. 기본값 — 심사자가 그냥 돌려도 돈다.
#   bedrock = Amazon Bedrock. AWS 자격증명이 있어야 하고 호출마다 과금된다.
#   ⚠️ 기본값을 bedrock 으로 두지 않는다 — 모르는 사이에 유료 호출이 나가면 안 된다.
PROVIDER = os.getenv("SHIPPER_PROVIDER", "ollama").lower()
BEDROCK_MODEL_ID = os.getenv("SHIPPER_BEDROCK_MODEL", "us.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))


def model_label() -> str:
    """화면·측정 기록에 남길 «어느 모델로 답했나». 이 값이 없으면 두 측정을 못 견준다."""
    if PROVIDER == "bedrock":
        return f"bedrock:{BEDROCK_MODEL_ID}@{BEDROCK_REGION}"
    return f"ollama:{MODEL_ID}"


def build_model():
    if PROVIDER == "bedrock":
        from strands.models import BedrockModel  # 지연 import — ollama 만 쓰는 기계에 boto3 요구 X

        return BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)
    if PROVIDER != "ollama":
        raise ValueError(f"SHIPPER_PROVIDER 는 ollama 또는 bedrock 이어야 한다: {PROVIDER!r}")
    return OllamaModel(host=OLLAMA, model_id=MODEL_ID)


def build_agent() -> Agent:
    """### 모델을 «명시» 한다. 안 하면 Strands 기본값이 유료 Bedrock 이다.

    🔴 `callback_handler=None` 도 «명시» 다. 기본 스트리밍 핸들러를 쓰면
    작은 모델이 tool-call 을 «텍스트로» 뱉는 일이 잦다 — 실측(n=6):
        기본 handler   성공 **2/6**
        handler=None   성공 **5/6**
    ⇒ 스트리밍 출력을 잃는 대신 도구가 실제로 돈다. 데모에는 후자가 필요하다.
    """
    return Agent(
        model=build_model(),
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


def _mismatched_product(q: str, messages) -> str | None:
    """모델이 도구에 넘긴 품목이 «질문에 없는 낱말» 이면 그것을 돌려준다.

    🔴 **왜 생겼나** (2026-08-31, 최종 영상 125초 화면 실측):
       화면에 ### `2026-08-28 れ京鴝: 답할 수 없다` 가 떴다. 품목명이 오염된 채다.

    ### ⇒ 우리 방어의 «범위» 가 결함의 «범위» 보다 좁았다.
       · 막고 있던 것 = 모델이 **답변 문장**을 쓰는 것 (`_tool_headline`)
       · 안 막던 것   = ### 모델이 **도구 인자**를 오염시키는 것
       그 오염이 «코드가 만든 문장» 에 실려 나온다.
       ### ★ 그래서 더 나쁘다 — 형식이 완벽해서 권위 있어 보인다.
         (`available_dates` 건과 같은 형태다. 위 주석 참조.)

    ### ⚠️ 이건 우리가 슬라이드에서 «자랑하는» 바로 그 실패다 —
       *"In 4 of 6 runs it mixed in other languages."* 그 영상의 시연 화면에 섞여 있었다.

    판정 = **질문 문자열에 그 낱말이 있나.** 사람이 쓴 질문이 기준이다.
    ⚠️ 짧은 품목명이 우연히 포함될 수 있다(미탐 쪽). **안전 방향이라 그대로 둔다** —
       놓치면 종전과 같고, 과하게 잡으면 멀쩡한 회차를 버린다.
    ⚠️ `input` 이 없거나 `product` 가 없으면 **판정하지 않는다**(None). 지어내지 않는다.

    ### strands 없이 시험할 수 있게 `messages`(dict 리스트)만 받는다.
    """
    for m in messages or []:
        for c in (m.get("content") or []):
            if not isinstance(c, dict):
                continue
            tu = c.get("toolUse")
            if not isinstance(tu, dict) or tu.get("name") != "shipping_market_advice":
                continue
            prod = (tu.get("input") or {}).get("product")
            if isinstance(prod, str) and prod.strip() and prod.strip() not in q:
                return prod.strip()
    return None


# 구분자형(2026-08-28 · 2026.8.28 · 2026/8/28) 과 한국어형(2026년 8월 28일) 둘 다.
# 🔴 한국어형은 2026-09-13 에 추가했다 — 그전에는 `2026년 8월 30일 배추` 가 «날짜 미명시» 로 읽혀
#    모델이 다른 날을 조회해도 통과했다(CO 적대검증 R1). 사용자가 한국어로 묻는 제품인데 가드는 영문 형식만 봤다.
_DATE_RE = re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})\s*일?")


def _asked_dates(q: str) -> list[str]:
    """질문에 «명시된» 날짜 전부(YYYY-MM-DD 정규화, 순서 유지·중복 제거). 없으면 빈 목록."""
    out: list[str] = []
    for y, mo, d in _DATE_RE.findall(q or ""):
        try:
            iso = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            continue
        if iso not in out:
            out.append(iso)
    return out


def _asked_date(q: str) -> str | None:
    """질문의 날짜가 «정확히 하나» 일 때만 그 날짜. 없거나 둘 이상이면 None — 지어내지 않는다."""
    ds = _asked_dates(q)
    return ds[0] if len(ds) == 1 else None


def _mismatched_date(asked: str | None, got: str | None) -> str | None:
    """사용자가 날짜를 명시했는데 도구가 «다른 날짜» 를 봤으면 그 날짜를 돌려준다 (CO M4).

    실물(합성 재현): 질문 «2026-08-30 배추» 에 모델이 date=2026-08-28 을 넘겼고 그날 추천이 «정상 답» 으로 나갔다.
    품목만 대조하던 가드의 범위가 결함의 범위보다 좁았다. 날짜 미명시면 판정하지 않는다(None).
    """
    if asked and got and asked != got:
        return got
    return None


def _advice_calls(messages) -> int:
    """이 시도에서 `shipping_market_advice` 가 몇 번 불렸나. ### 둘 이상이면 «어느 답인가» 가 모호하다 (CO M3)."""
    n = 0
    for m in messages or []:
        for c in (m.get("content") or []):
            if isinstance(c, dict) and (c.get("toolUse") or {}).get("name") == "shipping_market_advice":
                n += 1
    return n


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
    r = run(q, retries=retries, log=lambda s: print(f"  [{s}]"))
    for line in r["screen"]:
        print(line)
    print(f"\n[{r['seconds']:.1f}초]")


def run(q: str, retries: int = 5, log=None) -> dict:
    """`ask()` 의 본체. ### 화면 대신 «구조» 를 돌려준다 — CLI 와 웹 UI 가 같은 경로를 탄다.

    돌려주는 것:
      kind      answer | refused_bad_item | refused_leak | refused_no_tool | error
      headline  도구가 쓴 [한 줄] (answer 일 때만. 코드가 만들었고 모델을 안 거쳤다)
      screen    CLI 가 그대로 찍는 줄들 (옛 ask() 출력과 같다)
      evidence  tools.last_as_dict() — 같은 호출이 만든 구조화 근거 (없으면 {})
      attempts  실제로 돈 회차 수 · seconds · model · tool_text(도구 원문) · model_text
    """
    import tools as _tools  # 지연 — LAST 를 읽으려고

    # 🔴 CO 적대검증(2026-09-12, review-afh-web-plan-14883-14897) 이 합성 재현으로 잡은 넷을 여기서 막는다:
    #   M1 거절 screen 에 모델 문장(근거 없는 가격)이 실렸다        → 모델 문장은 SHOW_MODEL_TEXT 없이는 어디에도 안 싣는다
    #   M2 재시도 뒤 «이전 시도» 의 headline·evidence 가 남았다      → 시도마다 LAST·headline·bad_item 초기화, 채택된 시도만 반환
    #   M3 headline(호출 A) + evidence(호출 B) 가 합쳐졌다           → 둘 다 tools.LAST 한 단위에서 꺼낸다 + 호출 2회 이상이면 거절
    #   M4 질문 날짜 ≠ 조회 날짜인데 정상 답으로 나갔다               → _mismatched_date
    asked_all = _asked_dates(q)
    asked_date = asked_all[0] if len(asked_all) == 1 else None
    # 🔴 질문에 날짜가 둘 이상이면 «첫 것을 채택» 하지 않는다 — 어느 날을 묻는지 우리가 모른다 (CO R1).
    #   실물: `2026-08-28 말고 2026-08-30 배추` 에서 첫 날짜가 채택돼 08-28 가격이 정상 답으로 나갔다.
    multi_date = len(asked_all) > 1
    t0 = time.time()
    attempts = 0
    err = None
    # 채택된 시도의 상태 — 매 시도 «새로» 만든다. 이전 시도 것은 절대 안 남긴다.
    out, headline, bad_item, bad_date, n_calls = "", None, None, None, 0
    for attempt in range(retries + 1):
        attempts = attempt + 1
        out, headline, bad_item, bad_date, n_calls = "", None, None, None, 0
        _tools.LAST.clear()
        try:
            agent = build_agent()          # 모델 생성 실패도 구조화된 error 로 (CO §3)
            out = str(agent(q))
        except Exception as e:
            err = type(e).__name__          # ### 종류만. 메시지 본문은 응답에 안 싣는다 (CO §3 오류 상세 노출)
            logging.getLogger(__name__).warning("model call failed: %s: %s", type(e).__name__, e)
            out = ""
            break
        n_calls = _advice_calls(agent.messages)
        unit = _tools.LAST                  # ### 이 시도에서 도구가 마지막으로 만든 «headline+Evidence 한 단위»
        headline = unit.get("headline") if (n_calls >= 1 and _tool_headline(agent)) else None
        bad_item = _mismatched_product(q, agent.messages)
        bad_date = _mismatched_date(asked_date, unit.get("date")) if headline else None
        if headline and multi_date:
            bad_date = unit.get("date")     # 어느 날을 물었는지 모른다 ⇒ 조회한 날을 밝히고 거절한다
        if headline and n_calls == 1 and not _leaked(out) and not bad_item and not bad_date:
            break
        # ### 재시도 사유. 전부 «근거 없는 답» 으로 끝나는 것들이다.
        #   ⓐ 도구 호출이 텍스트로 샜다
        #   ⓑ 모델이 «다른 도구» 를 불렀다 — 실측에서 `available_dates` 를 부르고 날짜 목록을 답인 양 내놓았다
        #   ⓒ 🔴 모델이 품목 이름을 바꿔 넘겼다 (2026-08-31) — 최종 영상 화면에 `れ京鴝` 가 떴다
        #   ⓓ 🔴 모델이 질문과 다른 날짜를 넘겼다 (2026-09-12, CO M4)
        #   ⓔ 🔴 판정 도구를 두 번 이상 불렀다 (2026-09-12, CO M3) — 어느 답인지 모호하다
        if _leaked(out):
            why = "도구 호출이 텍스트로 샜다"
        elif bad_item:
            why = f"모델이 품목을 '{bad_item}' 로 바꿔 넘겼다"
        elif bad_date:
            why = f"모델이 날짜를 {bad_date} 로 바꿔 넘겼다 (질문은 {asked_date})"
        elif n_calls > 1:
            why = f"판정 도구를 {n_calls}번 불렀다"
        else:
            why = "이 질문에 맞는 도구를 안 불렀다"
        if attempt < retries and log:
            log(f"{why} — 새 세션으로 재시도 {attempt + 1}/{retries}")
    dt = time.time() - t0

    # 🔴 재시도를 다 써도 오염돼 있으면 그 답은 «안 내놓는다» (2026-08-31). 가드가 재시도만 늘리면 소용없다.
    #
    # ### 누수(`_leaked`)는 «여기» 목록에 «일부러» 없다 — 정책을 명시한다 (CO R2, 2026-09-13):
    #   도구가 제대로 돌아 headline 이 나왔으면 그 답의 근거는 코드가 계산한 것이고, 모델이 그 뒤에
    #   호출 JSON 을 글자로 뱉은 것은 «답의 근거» 를 바꾸지 않는다. 그 원문은 화면에 안 나간다.
    #   ### 누수가 답을 막아야 하는 경우는 «도구가 아예 안 돈» 때이고, 그건 headline 이 없어 아래 refused_leak 로 간다.
    #   ⚠️ 그래서 위 재시도 루프는 누수를 «다시 시도할 사유» 로는 쓰되(깨끗한 회차를 선호한다)
    #      소진 뒤 근거 있는 답을 버리지는 않는다. 둘은 다른 판단이다.
    if bad_item or bad_date or n_calls > 1:
        headline = None

    screen: list[str] = []
    model_text = out.strip() if (out and not _leaked(out) and not err) else ""
    show_model = bool(os.getenv("SHOW_MODEL_TEXT")) and bool(model_text)
    if err:
        kind = "error"
        screen.append(f"\n🔴 모델 호출이 실패했다({err}). 답을 내지 않는다.")
    elif headline:
        kind = "answer"
        # ### 답은 이 줄이다. 코드가 만들었고 모델을 안 거쳤다.
        screen.append(f"\n{headline}")
        # ⚠️ 모델이 다시 쓴 문장은 «기본으로 안 보여준다» — 같은 실행에서 그 문장이 「물량 1,648」을
        #    «1,648건» 이라 갈아 붙였다. 보고 싶으면 SHOW_MODEL_TEXT=1.
        if show_model:
            screen.append(f"\n  (모델이 다시 쓴 것 — 참고용, 권위는 위 줄에 있다: {model_text[:160]})")
    elif bad_item:
        kind = "refused_bad_item"
        screen.append(f"\n🔴 모델이 품목을 '{bad_item}' 로 바꿔 넘겼다. "
                      "답을 내지 않는다 — 묻지 않은 것에 답하는 것보다 낫다.")
    elif bad_date:
        kind = "refused_bad_date"
        if multi_date:
            screen.append(f"\n🔴 질문에 날짜가 여럿이다({', '.join(asked_all)}). 모델은 {bad_date} 를 조회했다. "
                          "어느 날을 묻는지 알 수 없어 답을 내지 않는다 — 날짜 하나로 다시 물을 것.")
        else:
            screen.append(f"\n🔴 질문은 {asked_date} 인데 모델이 {bad_date} 자료를 조회했다. "
                          "답을 내지 않는다 — 다른 날의 값을 오늘 것처럼 내놓는 것보다 낫다.")
    elif n_calls > 1:
        kind = "refused_multi"
        screen.append(f"\n🔴 판정 도구가 {n_calls}번 불렸다. 어느 것이 답인지 모호해 답을 내지 않는다. "
                      "품목 하나·날짜 하나로 다시 물을 것.")
    elif _leaked(out):
        kind = "refused_leak"
        screen.append("\n🔴 도구 호출이 계속 샌다. 답을 내지 않는다 — 지어내는 것보다 낫다.")
    else:
        kind = "refused_no_tool"
        # ### 도구를 «안 불렀거나 다른 도구를 불렀다» = 이 질문의 근거가 없다.
        #   🔴 여기에 모델 문장을 붙이지 않는다 (CO M1: 그 문장에 근거 없는 가격이 실려 화면 제목이 됐다).
        screen.append("\n🔴 이 질문에 답할 도구가 실행되지 않았다. 근거가 없어 답을 내지 않는다.")
        if show_model:
            screen.append(f"  (모델이 쓴 것 — 근거 없음: {model_text[:120]})")

    # «도구가 거절했다»(근거 부족 · headline 있음 · «답할 수 없다») 와 «가드가 거절했다»(headline 없음) 는 다른 사실이다.
    tool_refused = bool(headline) and "답할 수 없다" in headline
    return {
        "question": q,
        "kind": kind,
        "tool_refused": tool_refused,
        "headline": headline,
        "bad_item": bad_item,
        "bad_date": bad_date,
        "asked_date": asked_date,
        "asked_dates": asked_all,
        "n_tool_calls": n_calls,
        "screen": screen,
        # ### 근거는 «채택된 답» 에만 딸려 나간다 (CO M2). 오류·가드 거절엔 가격 있는 표를 안 보낸다.
        "evidence": _tools.last_as_dict() if kind == "answer" else {},
        "attempts": attempts,
        "retries": retries,
        "seconds": round(dt, 1),
        "model": model_label(),
        # ### 모델 문장은 CLI 와 같은 계약 — SHOW_MODEL_TEXT 가 없으면 웹에도 안 보낸다(TT30).
        "model_text": model_text[:400] if show_model else "",
        "error": err,
    }


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
