import os,sys,json
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import load_day, filter_product
d = load_day("2026-08-28")
m = filter_product(d.items, "복숭아")
print(f"전체 {len(d.items):,} / 복숭아 매칭 {len(m):,}  ({len(m)/len(d.items)*100:.1f}%)")
print("\n매칭된 품목명(gds_mclsf_nm) 상위:")
for k,v in Counter((x.get("gds_mclsf_nm") or "").strip() for x in m).most_common(8): print(f"   {k!r}: {v:,}")
print("\n매칭된 품종명(gds_sclsf_nm) 상위:")
for k,v in Counter((x.get("gds_sclsf_nm") or "").strip() for x in m).most_common(8): print(f"   {k!r}: {v:,}")
print("\n=== 이상치 확인: 원/kg 상위 5 ===")
rows=[]
for x in m:
    try: p=float(x.get("scsbd_prc",0)); u=float(x.get("unit_qty",0))
    except: continue
    if p>0 and u>0: rows.append((p/u, x.get("whsl_mrkt_nm"), p, u, x.get("gds_sclsf_nm"), x.get("unit_nm"), x.get("pkg_nm")))
rows.sort(reverse=True)
for r in rows[:5]: print(f"   {r[0]:>12,.0f}원/kg | {r[1]} | 단가 {r[2]:,.0f} / 단위중량 {r[3]} | {r[4]} | 단위 {r[5]} | 포장 {r[6]}")
print("   ...")
for r in rows[-3:]: print(f"   {r[0]:>12,.0f}원/kg | {r[1]} | 단가 {r[2]:,.0f} / 단위중량 {r[3]} | {r[4]}")
import statistics
vals=[r[0] for r in rows]
print(f"\n원/kg 분포: 중앙 {statistics.median(vals):,.0f} / 평균 {statistics.mean(vals):,.0f} / 최대 {max(vals):,.0f}")
print(f"   -> 평균이 중앙의 {statistics.mean(vals)/statistics.median(vals):.1f}배. 꼬리가 평균을 끌고 있다")
