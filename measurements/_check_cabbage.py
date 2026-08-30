import os, sys, statistics
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import load_day, filter_product
d = load_day("2026-08-28"); m = filter_product(d.items, "배추")
for mkt in ["춘천", "안산"]:
    sub = [x for x in m if (x.get("whsl_mrkt_nm") or "").strip() == mkt]
    rows=[]
    for x in sub:
        try: p=float(x.get("scsbd_prc",0)); u=float(x.get("unit_qty",0))
        except: continue
        if p>0 and u>0: rows.append((p/u, p, u, x.get("gds_sclsf_nm"), x.get("unit_nm"), x.get("pkg_nm"), x.get("qty")))
    rows.sort()
    print(f"\n=== {mkt} · 배추 {len(sub)}건 (환산 {len(rows)}건) ===")
    print(f"  원/kg 중앙 {statistics.median([r[0] for r in rows]):,.0f}")
    for r in rows[:3]: print(f"   낮음 {r[0]:>9,.0f}원/kg | 단가{r[1]:>8,.0f} / 단위중량 {r[2]:>5} | {r[3]} | 단위 {r[4]} | 포장 {r[5]} | 수량 {r[6]}")
    for r in rows[-3:]: print(f"   높음 {r[0]:>9,.0f}원/kg | 단가{r[1]:>8,.0f} / 단위중량 {r[2]:>5} | {r[3]} | 단위 {r[4]} | 포장 {r[5]} | 수량 {r[6]}")
    print("   단위 분포:", dict(Counter((x.get("unit_nm") or "").strip() for x in sub)))
