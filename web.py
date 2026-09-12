"""
웹 UI — 같은 에이전트, 같은 도구, 같은 판정. 화면만 붙였다 (2026-09-12).

돌리기:
    ../.venv/Scripts/python.exe web.py            # http://127.0.0.1:8620
    SHIPPER_WEB_PORT=8080 python web.py

### 설계 한 줄: 판정은 여전히 evidence.py 가 하고, 모델은 도구를 고른다. 이 파일은 그 결과를 «보여줄» 뿐이다.
  · /api/ask  → agent.run()  — CLI 가 타는 경로 그대로. UI 전용 경로를 만들지 않는다.
  · 표의 숫자 = 도구가 그 호출에서 계산한 Evidence(tools.LAST). 두 번 계산하지 않는다.
  · 거절이면 가격을 «안 보낸다» — render() 가 텍스트에서 뺀 이유와 같다. 사람도 그 값을 인용한다.
  · 요청은 한 번에 하나(lock). tools.LAST 가 프로세스 전역이라 동시 요청이면 섞인다.

의존성: starlette · uvicorn (둘 다 strands 가 이미 끌고 온다). 새 패키지 없음.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.applications import Starlette  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import HTMLResponse, JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

import agent as _agent  # noqa: E402
from data import cached_dates_detail  # noqa: E402

PORT = int(os.getenv("SHIPPER_WEB_PORT", "8620"))
HERE = Path(__file__).resolve().parent
_LOCK = asyncio.Lock()


async def index(_: Request) -> HTMLResponse:
    return HTMLResponse((HERE / "web_index.html").read_text(encoding="utf-8"))


async def api_dates(_: Request) -> JSONResponse:
    """무엇까지 물을 수 있나. ### 모델을 안 거친다 — 자료 목록은 코드가 안다."""
    detail = cached_dates_detail()
    return JSONResponse(
        {
            "dates": [{"date": d, "products": p} for d, p in detail],
            "model": _agent.model_label(),
        }
    )


async def api_ask(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "JSON body 가 필요하다: {\"q\": \"...\"}"}, status_code=400)
    q = str(body.get("q", "")).strip()
    if not q:
        return JSONResponse({"error": "질문이 비어 있다"}, status_code=400)
    if len(q) > 300:
        return JSONResponse({"error": "질문이 너무 길다 (300자)"}, status_code=400)
    async with _LOCK:
        r = await run_in_threadpool(_agent.run, q)
    return JSONResponse(r)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/dates", api_dates),
        Route("/api/ask", api_ask, methods=["POST"]),
    ]
)


def main() -> int:
    import uvicorn

    _agent._pin_demo_cache()  # CLI 와 같은 자료로 고정 — 심사자 기계와 개발자 기계가 같은 화면
    print(f"[web] http://127.0.0.1:{PORT}  ·  model = {_agent.model_label()}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
