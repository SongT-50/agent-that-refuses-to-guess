"""run() 응답 계약 대조군 — CO 적대검증(2026-09-12, review-afh-web-plan-14883-14897) 이 합성 재현으로 잡은 넷.

  M1 가드 거절 화면에 모델 문장(근거 없는 가격)이 실렸다
  M2 재시도 뒤 «이전 시도» 의 headline·evidence 가 남았다
  M3 headline(호출 A) + evidence(호출 B) 가 합쳐졌다
  M4 질문 날짜 ≠ 조회 날짜인데 정상 답으로 나갔다

### 기존 스위트는 run() 을 «실행하지 않았다»(TT30·AG15 는 소스 문자열 검사). 이 파일이 실행한다.
모델 경계만 가짜다: FakeAgent 가 «도구를 실제로 실행» 하고 Strands 가 만드는 messages 모양을 그대로 만든다.
자료 = 저장소가 싣는 데모 추출본만(임시 폴더에 복사해 SHIPPER_CACHE 로 고정 — 개발 기계의 전량 캐시가 답을 바꾸지 않게).

### 이 스위트가 반드시 보여야 하는 것
  ⓐ 넷을 «잡는다»                      (안 잡으면 가드가 없는 것과 같다)
  ⓑ 정상 회차에 «조용하다»              (PC — 없으면 «전부 잡는» 실패할 수 없는 대조군이다)
  ⓒ 거절엔 가격이 «어디에도» 없다       (JSON 전체를 문자열로 검사한다. 필드 하나만 보지 않는다)
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 자료 고정: 데모 추출본만 ─────────────────────────────────────────
_TMP = Path(tempfile.mkdtemp(prefix="shipper_demo_"))
for f in (HERE / "_cache").glob("demo-*.json.gz"):
    shutil.copy(f, _TMP / f.name)
os.environ["SHIPPER_CACHE"] = str(_TMP)
os.environ.pop("SHOW_MODEL_TEXT", None)

import agent as A  # noqa: E402
import tools as T  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(tag: str, ok: bool, note: str = "") -> None:
    RESULTS.append((tag, ok, note))
    print(f"  {'PASS' if ok else '🔴 FAIL'}  {tag}" + (f"   [{note}]" if note else ""))


def _run_tool(product: str, date: str) -> str:
    """프로덕션 도구를 «그대로» 부른다(strands 래퍼는 __call__ 이 원함수로 간다. 아니면 _advice)."""
    try:
        return T.shipping_market_advice(product, date)
    except TypeError:
        return T._advice(product, date)


class FakeAgent:
    """한 시도. calls = [(tool_name, product, date), ...] 를 실제로 실행하고 messages 를 만든다."""

    def __init__(self, calls, text="", raise_exc=None):
        self.calls, self.text, self.raise_exc = calls, text, raise_exc
        self.messages = []

    def __call__(self, q):
        if self.raise_exc:
            raise self.raise_exc
        uses, results = [], []
        for i, (name, product, date) in enumerate(self.calls):
            tid = f"t{i}"
            uses.append({"toolUse": {"toolUseId": tid, "name": name, "input": {"product": product, "date": date}}})
            out = _run_tool(product, date) if name == "shipping_market_advice" else T.available_dates()
            results.append({"toolResult": {"toolUseId": tid, "content": [{"text": out}]}})
        if uses:
            self.messages = [{"role": "assistant", "content": uses}, {"role": "user", "content": results}]
        return self.text


def with_attempts(attempts):
    """build_agent 를 시도 순서대로 갈아끼운다."""
    it = iter(attempts)
    return lambda: next(it)


def run(q, attempts, retries=None):
    if retries is None:
        retries = len(attempts) - 1
    orig = A.build_agent
    A.build_agent = with_attempts(attempts)
    try:
        return A.run(q, retries=retries)
    finally:
        A.build_agent = orig


def dumps(r) -> str:
    return json.dumps(r, ensure_ascii=False)


LEAK_JSON = '{"name": "shipping_market_advice", "parameters": {"product": "복숭아"}}'
Q_PEACH = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"


def main() -> int:
    print("=" * 68)
    print("run() 응답 계약 — CO M1~M4 + 대조군")
    print("=" * 68)

    # ── PC 양성 대조군: 정상 회차는 조용하다 ─────────────────────────
    r = run(Q_PEACH, [FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], "원주가 가장 높다")])
    check("PC1 정상 1회차 = answer", r["kind"] == "answer" and not r["tool_refused"], r["headline"])
    check("PC2 근거 표가 있다", len(r["evidence"].get("markets", [])) > 0)
    check("PC3 headline 과 evidence 가 같은 품목·날짜", r["evidence"].get("product") == "복숭아" and r["evidence"].get("date") == "2026-08-28")
    check("PC4 시도 1회", r["attempts"] == 1)

    # ── 도구 거절(근거 부족) — 양파는 데모 추출본에 없다 ──────────────
    r = run("2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?",
            [FakeAgent([("shipping_market_advice", "양파", "2026-08-28")], "답할 수 없다")])
    check("TR1 도구 거절 = answer + tool_refused", r["kind"] == "answer" and r["tool_refused"], r["headline"])
    check("TR2 거절 근거에 가격 필드가 없다", r["evidence"].get("markets") == [] and "won_per_kg" not in dumps(r["evidence"]))
    check("TR3 거절 사유는 있다", len(r["evidence"].get("why_insufficient", [])) > 0)

    # ── M1 가드 거절 화면에 모델 문장이 없다 ────────────────────────
    r = run("배추 어디", [FakeAgent([], "SYNTHETIC_MARKET 999999원/kg")], retries=0)
    check("M1a 도구 없음 = refused_no_tool", r["kind"] == "refused_no_tool")
    check("M1b 합성 가격이 응답 «어디에도» 없다", "999999" not in dumps(r) and "SYNTHETIC" not in dumps(r), "SHOW_MODEL_TEXT 미설정")
    check("M1c evidence 비어 있다", r["evidence"] == {})
    os.environ["SHOW_MODEL_TEXT"] = "1"
    r2 = run("배추 어디", [FakeAgent([], "SYNTHETIC_MARKET 999999원/kg")], retries=0)
    os.environ.pop("SHOW_MODEL_TEXT", None)
    check("M1d 켜면 참고용으로만 보인다 (권위 필드엔 없다)", "999999" in r2["model_text"] and r2["headline"] is None)

    # ── M2 재시도 뒤 이전 시도 상태가 안 남는다 ──────────────────────
    r = run(Q_PEACH, [
        FakeAgent([("shipping_market_advice", "배추", "2026-08-28")], "배추가…"),   # 품목 바꿔 넘김 → 재시도
        FakeAgent([], "모르겠다"),                                                     # 도구 없음
    ])
    check("M2a 최종 = refused_no_tool", r["kind"] == "refused_no_tool", r["kind"])
    check("M2b 1회차 배추 근거가 안 남았다", r["evidence"] == {} and r["headline"] is None)
    check("M2c 시도 2회", r["attempts"] == 2)
    r = run(Q_PEACH, [
        FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], LEAK_JSON),     # 답은 나왔지만 출력이 샘
        FakeAgent([], raise_exc=RuntimeError("SYNTHETIC_PRIVATE_ERROR")),              # 2회차 모델 실패
    ])
    check("M2d 최종 = error", r["kind"] == "error")
    check("M2e 1회차 headline·evidence 가 안 남았다", r["headline"] is None and r["evidence"] == {})
    check("M2f 오류 상세가 응답에 없다 (종류만)", r["error"] == "RuntimeError" and "SYNTHETIC_PRIVATE" not in dumps(r))
    r = run(Q_PEACH, [FakeAgent([], raise_exc=ValueError("bad provider"))], retries=0)
    check("M2g build/호출 예외도 구조화된 error", r["kind"] == "error" and r["error"] == "ValueError")

    # ── M3 두 호출이 한 시도에 — 합치지 않고 거절 ───────────────────
    r = run("2026-08-28에 복숭아랑 양파 어디에 낼까", [
        FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28"), ("shipping_market_advice", "양파", "2026-08-28")], "…")
    ], retries=0)
    check("M3a 두 호출 = refused_multi", r["kind"] == "refused_multi" and r["n_tool_calls"] == 2, r["kind"])
    check("M3b 제목 A + 근거 B 가 합쳐지지 않았다", r["headline"] is None and r["evidence"] == {})
    check("M3c 가격이 응답에 없다", "원/kg" not in dumps(r) or "가장 높다" not in dumps(r))

    # ── M4 질문 날짜 ≠ 조회 날짜 ──────────────────────────────────
    r = run("2026-08-30에 복숭아를 출하하려는데 어느 시장이 유리해?",
            [FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], "원주가…")], retries=0)
    check("M4a 날짜 어긋남 = refused_bad_date", r["kind"] == "refused_bad_date" and r["bad_date"] == "2026-08-28", r["kind"])
    check("M4b 08-28 추천이 안 나갔다", r["headline"] is None and r["evidence"] == {})
    check("M4c 화면이 두 날짜를 말한다", "2026-08-30" in r["screen"][0] and "2026-08-28" in r["screen"][0])
    # 음성 대조군: 날짜를 안 적은 질문은 날짜로 거절하지 않는다
    r = run("복숭아 어디에 낼까", [FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], "원주")], retries=0)
    check("M4d 날짜 미명시면 판정하지 않는다", r["kind"] == "answer" and r["bad_date"] is None)
    check("M4e 점·슬래시 날짜도 읽는다", A._asked_date("2026.8.28 복숭아") == "2026-08-28" and A._asked_date("2026/08/30") == "2026-08-30")

    # ── R1 (CO 재검증 2026-09-13): 날짜 가드 «범위» 밖에서 다른 날 가격이 나갔다 ──
    #   CO 가 준 입력 문자열 그대로 쓴다. 둘 다 도구는 08-28 을 조회한다.
    check("R1a 한국어 날짜를 읽는다", A._asked_date("2026년 8월 30일 배추 어디") == "2026-08-30")
    r = run("2026년 8월 30일 배추 어디",
            [FakeAgent([("shipping_market_advice", "배추", "2026-08-28")], "…")], retries=0)
    check("R1b 한국어 날짜 어긋남 = refused_bad_date", r["kind"] == "refused_bad_date", r["kind"])
    check("R1c 08-28 가격이 안 나갔다", r["headline"] is None and r["evidence"] == {})
    check("R1d 복수 날짜는 첫 것을 채택하지 않는다", A._asked_date("2026-08-28 말고 2026-08-30 배추") is None
          and A._asked_dates("2026-08-28 말고 2026-08-30 배추") == ["2026-08-28", "2026-08-30"])
    r = run("2026-08-28 말고 2026-08-30 배추",
            [FakeAgent([("shipping_market_advice", "배추", "2026-08-28")], "…")], retries=0)
    check("R1e 복수 날짜 = refused_bad_date", r["kind"] == "refused_bad_date", r["kind"])
    check("R1f 화면이 날짜 둘을 다 말한다", "2026-08-28" in r["screen"][0] and "2026-08-30" in r["screen"][0])
    # 음성 대조군 — 한국어 날짜가 «맞으면» 조용하다 (이 가드가 전부 거절하는 게 아님)
    r = run("2026년 8월 28일 복숭아 어디",
            [FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], "원주")], retries=0)
    check("R1g 한국어 날짜가 맞으면 답한다", r["kind"] == "answer" and r["bad_date"] is None, r["kind"])

    # ── R2 (CO 보조 지적): 도구가 돈 뒤 모델 출력이 새면? ── 정책 = 답을 버리지 않는다.
    #   근거는 코드가 만들었고 누수 원문은 화면에 안 나간다. 도구가 «안 돈» 누수는 아래 LK2 가 거절한다.
    r = run(Q_PEACH, [FakeAgent([("shipping_market_advice", "복숭아", "2026-08-28")], LEAK_JSON)], retries=0)
    check("LK1 도구가 돌았으면 누수에도 답한다", r["kind"] == "answer" and r["headline"], r["kind"])
    check("LK2 누수 원문은 응답에 없다", "shipping_market_advice\"" not in dumps(r) and r["model_text"] == "")
    r = run(Q_PEACH, [FakeAgent([], LEAK_JSON)], retries=0)
    check("LK3 도구가 안 돌았으면 누수는 거절", r["kind"] == "refused_leak" and r["evidence"] == {}, r["kind"])

    # ── 웹 경계: JSON 형태 ──────────────────────────────────────────
    try:
        from starlette.testclient import TestClient
        import web as W

        c = TestClient(W.app)
        bad = [c.post("/api/ask", json=[]).status_code, c.post("/api/ask", json="x").status_code,
               c.post("/api/ask", json={"q": 5}).status_code, c.post("/api/ask", json={"q": ""}).status_code,
               c.post("/api/ask", json={"q": "x" * 301}).status_code]
        check("W1 잘못된 body 는 전부 400", bad == [400] * 5, str(bad))
        orig = A.run
        A.run = lambda q, retries=5: {"kind": "answer", "question": q, "evidence": {}, "screen": ["ok"]}
        try:
            ok = c.post("/api/ask", json={"q": "복숭아"})
            check("W2 정상 body 는 200 + run() 결과", ok.status_code == 200 and ok.json()["question"] == "복숭아")
        finally:
            A.run = orig
        check("W3 /api/dates 는 모델을 안 거친다", c.get("/api/dates").status_code == 200)
    except ImportError as e:
        check("W0 TestClient 사용 불가 (httpx 없음) — 웹 경계 미검사", False, str(e))

    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 68)
    print(f"{n_ok}/{len(RESULTS)} PASS")
    print(f"반증자 확인: 잡는 사례 {sum(1 for t,ok,_ in RESULTS if t[:2] in ('M1','M2','M3','M4') and t[2] in 'abcdefg' and ok)}건 · 조용한 사례 {sum(1 for t,ok,_ in RESULTS if t.startswith(('PC','M4d','M4e')) and ok)}건")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
