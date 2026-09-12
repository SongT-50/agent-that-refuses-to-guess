"""에이전트 층 대조군 — **도구 «인자» 오염을 잡나**

왜 이 파일이 생겼나 (2026-08-31):
  최종 제출 영상 125초 화면에 ### `2026-08-28 れ京鴝: 답할 수 없다` 가 떴다.
  품목명이 오염된 채 «코드가 만든 문장» 에 실려 나갔다.

### ⇒ 우리 방어의 범위가 결함의 범위보다 좁았다.
  · `_tool_headline` 이 막던 것 = 모델이 **답변 문장**을 쓰는 것
  · 아무도 안 막던 것        = ### 모델이 **도구 인자**를 오염시키는 것
  ### ★ 형식이 완벽해서 더 권위 있어 보인다. 그래서 아무도 못 봤다.

### 이 스위트가 반드시 보여야 하는 것:
  ⓐ 오염을 **잡는다**                  (안 잡으면 가드가 없는 것과 같다)
  ⓑ ### 정상 회차에 **조용하다**        (여기가 없으면 «전부 잡는» 실패할 수 없는 대조군이다)
  ⓒ 모르면 **판정하지 않는다**          (input 이 없을 때 지어내지 않는다)
  ⓓ ### 재시도를 다 써도 오염분을 **안 내놓는다** (가드가 재시도만 늘리면 소용없다)

⚠️ strands 를 안 탄다. `_mismatched_product` 는 messages(dict 리스트)만 받는다.
   ### 함수를 시험하는 게 아니라 «프로덕션이 부르는 그 형태» 로 부른다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS: list[tuple[str, bool, str]] = []


def check(tag: str, ok: bool, note: str = "") -> None:
    RESULTS.append((tag, ok, note))
    print(f"  {'PASS' if ok else '🔴 FAIL'}  {tag}" + (f"   [{note}]" if note else ""))


def msgs(product, tool="shipping_market_advice", with_input=True):
    """프로덕션이 보는 messages 모양 그대로 만든다."""
    tu = {"toolUseId": "t1", "name": tool}
    if with_input:
        tu["input"] = {"product": product, "date": "2026-08-28"}
    return [{"role": "assistant", "content": [{"toolUse": tu}]}]


def main() -> int:
    from agent import _mismatched_product as mp

    Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"

    # ── ⓐ 오염을 잡나 ──────────────────────────────────────────────
    # ### 실물이다. 최종 영상 화면에 실제로 뜬 문자열.
    check("AG01 실물 오염(れ京鴝)을 잡는다",
          mp(Q, msgs("れ京鴝")) == "れ京鴝", "영상 125초에 실제로 뜬 값")
    check("AG02 다른 언어 혼입을 잡는다", mp(Q, msgs("桃")) == "桃")
    check("AG03 베트남어 혼입을 잡는다", mp(Q, msgs("đào")) == "đào")
    check("AG04 엉뚱한 품목을 잡는다", mp(Q, msgs("양파")) == "양파")

    # ── ⓑ 정상에 조용한가 (### 과잉 시험 — 이게 없으면 실패할 수 없는 대조군) ──
    check("AG05 정상 품목엔 조용하다", mp(Q, msgs("복숭아")) is None,
          "질문에 있는 낱말")
    check("AG06 조사가 붙어도 조용하다",
          mp("2026-08-30에 배추를 출하하려는데?", msgs("배추")) is None)
    check("AG07 앞뒤 공백은 오탐이 아니다", mp(Q, msgs("  복숭아  ")) is None)

    # ── ⓒ 모르면 판정하지 않는다 (지어내지 않는다) ──────────────────
    check("AG08 input 이 없으면 판정 안 함",
          mp(Q, msgs("れ京鴝", with_input=False)) is None)
    check("AG09 다른 도구는 안 본다",
          mp(Q, msgs("れ京鴝", tool="available_dates")) is None)
    check("AG10 빈 messages 는 None", mp(Q, []) is None)
    check("AG11 None messages 도 안 터진다", mp(Q, None) is None)
    check("AG12 product 가 빈 문자열이면 판정 안 함", mp(Q, msgs("   ")) is None)
    check("AG13 product 가 문자열이 아니면 판정 안 함", mp(Q, msgs(123)) is None)

    # ── 형태가 깨진 입력에 예외를 던지지 않는다 ─────────────────────
    #   ### 던지면 그 자리를 모델이 채운다(test_tools ⓐ와 같은 원칙).
    try:
        mp(Q, [{"role": "assistant", "content": None}])
        mp(Q, [{"role": "assistant", "content": ["문자열"]}])
        mp(Q, [{}])
        check("AG14 깨진 messages 에도 예외를 안 던진다", True)
    except Exception as e:  # noqa: BLE001
        check("AG14 깨진 messages 에도 예외를 안 던진다", False, f"{type(e).__name__}")

    # ── ⓓ 재시도 소진 시 오염분을 안 내놓나 (### 소스코드 계약) ──────
    #   가드가 «재시도만 늘리고» 마지막 오염분을 그대로 출력하면 소용이 없다.
    #   그게 정확히 지금까지 일어나던 일이다.
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent.py"), encoding="utf-8").read()
    # 2026-09-12: 가드가 넓어졌다(품목 + 날짜 + 다중 호출, CO M3·M4). 계약은 «bad_item 이면 headline 을 버린다» 그대로.
    check("AG15 소진 시 headline 을 버린다",
          "if bad_item or bad_date or n_calls > 1:\n        headline = None" in src,
          "이 줄이 없으면 오염분이 화면에 나간다")
    check("AG16 거절 이유를 화면에 말한다",
          "로 바꿔 넘겼다. " in src)

    print("=" * 64)
    bad = [t for t, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} PASS")
    # ### 반증자 — 잡는 사례와 조용한 사례가 «둘 다» 있어야 한다.
    print(f"반증자 확인: 잡는 사례 4건 · 조용한 사례 3건 · 판정 보류 6건")
    if bad:
        print("🔴 실패:", ", ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
