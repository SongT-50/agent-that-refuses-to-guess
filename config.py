"""
경로·설정 한 곳 — **절대경로를 코드에 박지 않는다**

왜 고쳤나 (2026-08-30):
  9개 파일에 `C:\\Users\\<사용자명>\\...` 이 박혀 있었다. 두 가지가 동시에 문제였다.
    ⓐ 공개 저장소에 그대로 나가면 **사용자명이 노출**된다
    ⓑ 그리고 ### **다른 사람 기계에서는 아예 안 돈다** — 해커톤 요건이
       *"setup instructions needed to run the project"* 이고 심사자가 돌려볼 수 있다.
  ⇒ 위치는 «파일 기준 상대경로» 로 찾고, 없으면 «환경변수» 로 받는다.
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

# .env 는 저장소 어디에 있을지 모른다 — 위로 올라가며 찾는다.
def find_env() -> Path | None:
    override = os.getenv("SHIPPER_ENV_FILE")
    if override and Path(override).is_file():
        return Path(override)
    for d in [HERE, *HERE.parents]:
        p = d / ".env"
        if p.is_file():
            return p
    return None


def load_env() -> None:
    """`.env` 가 있으면 읽는다. 없어도 죽지 않는다 — 환경변수로 줄 수 있다."""
    p = find_env()
    if p is None:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(p)
    except ImportError:
        # dotenv 없이도 돌게 한다. 심사자 환경을 가정하지 않는다.
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def api_key() -> str:
    """data.go.kr 서비스 키. ### 값을 로그나 화면에 찍지 말 것."""
    load_env()
    return os.getenv("DATA_GO_KR_API_KEY", "")


CACHE_DIR = Path(os.getenv("SHIPPER_CACHE", HERE / "_cache"))

# 기존 MCP 서버 경로 — 이 저장소 밖에 있으면 환경변수로 알려준다.
def mcp_server_path() -> Path | None:
    override = os.getenv("KOREAN_AGRICULTURE_MCP")
    if override and Path(override).is_file():
        return Path(override)
    for d in [HERE, *HERE.parents]:
        p = d / "mcp-servers" / "korean-agriculture-mcp" / "server.py"
        if p.is_file():
            return p
    return None
