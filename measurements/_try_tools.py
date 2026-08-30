import logging, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
logging.getLogger("httpx").setLevel(logging.WARNING)
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import cached_dates, filter_product, load_day
from evidence import build_evidence, render

print("캐시된 날짜:", cached_dates())

def scene(tag, date, product):
    print("\n" + "="*70); print(f"[{tag}] {date} / {product}"); print("="*70)
    t0=time.time(); day = load_day(date); dt=time.time()-t0
    m = filter_product(day.items, product)
    ev = build_evidence(m, product, date, day_total=day.day_total, all_day_items=day.items)
    print(f"(자료: {day.source} · 그날 {day.day_total:,}건 중 {len(day.items):,}건 · 조회 {dt:.1f}초)")
    print(f"품목 매칭 {len(m)}건 · sufficient={ev.sufficient}")
    print(render(ev))

scene("장면1 전량 캐시", "2026-08-28", "복숭아")
scene("장면2 예산 조회(절단)", "2026-08-26", "복숭아")
