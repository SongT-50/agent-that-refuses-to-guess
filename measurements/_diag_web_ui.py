"""웹 UI 종단 실측 — /api/ask 가 CLI 와 같은 판정을 내나 (2026-09-12).

돌리기 (서버가 떠 있어야 한다: python web.py):
    python measurements/_diag_web_ui.py            # 세 장면 1회씩
    python measurements/_diag_web_ui.py --runs 4   # 세 장면 4회씩

기록하는 것 = kind · tool_refused · attempts · seconds · 표 행 수 · 거절 사유 · headline · model.
⚠️ curl 로 한글을 보내면 Windows 셸이 인코딩을 깨뜨려 400 이 난다(실측). 그래서 이 파일이 있다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

SCENES = [
    "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?",
    "2026-08-30에 배추를 출하하려는데 어느 시장이 유리해?",
    "2026-08-28에 양파를 출하하려는데 어느 시장이 유리해?",
]


def ask(base: str, q: str) -> dict:
    req = urllib.request.Request(
        f"{base}/api/ask",
        data=json.dumps({"q": q}).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8620")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rows = []
    for run in range(1, a.runs + 1):
        for i, q in enumerate(SCENES, 1):
            t0 = time.time()
            d = ask(a.base, q)
            ev = d.get("evidence") or {}
            row = {
                "run": run, "scene": i, "kind": d["kind"], "tool_refused": d["tool_refused"],
                "attempts": d["attempts"], "seconds": d["seconds"], "wall": round(time.time() - t0, 1),
                "n_markets_shown": len(ev.get("markets") or []), "why": ev.get("why_insufficient") or [],
                "headline": d.get("headline"), "model": d["model"],
                "non_korean_in_headline": bool(d.get("headline")) and any(
                    "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" or ("a" <= ch.lower() <= "z" and ch not in "kg")
                    for ch in (d.get("headline") or "").replace("kg", "")
                ),
            }
            rows.append(row)
            print(f"run{run} 장면{i}: {row['kind']} tool_refused={row['tool_refused']} "
                  f"시도 {row['attempts']} · {row['seconds']}s · 표 {row['n_markets_shown']}행 · {row['headline']}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"저장: {a.out}")
    expected = {1: ("answer", False), 2: ("answer", True), 3: ("answer", True)}
    ok = sum(1 for r in rows if (r["kind"], r["tool_refused"]) == expected[r["scene"]])
    print(f"기대 판정 일치 {ok}/{len(rows)} (장면1 답 · 장면2 거절=그날 0건 · 장면3 거절=못 봤다)")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
