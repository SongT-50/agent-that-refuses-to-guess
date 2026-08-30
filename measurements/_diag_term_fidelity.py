"""
용어를 바꿔 쓰나 — **«중앙값» 을 «평균» 이라 옮기는가**

팀원이 짚은 것: «더 큰 모델이 이 문제를 푼다» 고 쓰려면 그 비교가 있어야 한다.
### 그 전에 물을 것이 있다 — [한 줄] 통과 고침 뒤에도 이 문제가 «남아 있나».
안 재고 «큰 모델이 필요하다» 고 하면 그건 우리가 오늘 계속 잡은 그 형태다.

도구는 «중앙값» 이라 준다. 모델이 그것을 무엇이라 옮기는지 6회 센다.
"""
import logging, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import build_agent, _leaked

Q = "2026-08-28에 복숭아를 출하하려는데 어느 시장이 유리해?"
N = 6
swapped = kept = neither = 0
for i in range(1, N + 1):
    out = ""
    for _ in range(3):
        out = str(build_agent()(Q))
        if not _leaked(out):
            break
    # 🔴 1차 탐지기가 «중앙» 만 셌다. 모델은 «중간값»·«중간 giá»·«trung상» 으로 썼고
    #    ### 그건 의미 유지인데 내 검사기가 «용어 없음» 으로 셌다. 오늘 열 번째 계측기 결함.
    #    ⇒ 의미가 보존되는 표기를 전부 센다. 그리고 «평균» 계열과 갈라 센다.
    MED = r"중앙값?|중간\s*값|중간\s*giá|trung|median|중위"
    AVG = r"평균|average|mean"
    has_med = re.search(MED, out) is not None
    has_avg = re.search(AVG, out) is not None
    if has_avg and not has_med:
        swapped += 1; tag = "🔴 평균으로 바꿈"
    elif has_med:
        kept += 1; tag = "✅ 의미 유지"
    else:
        neither += 1; tag = "   용어 언급 없음"
    print(f"  {i}. {tag} | {out[:95]}")
print(f"\n중앙값 유지 {kept}/{N} · 평균으로 바꿈 {swapped}/{N} · 용어 언급 없음 {neither}/{N}")
print("⚠️ llama3.2:3b · 질문 1개 · n=6. Bedrock 비교는 «안 쟀다».")
