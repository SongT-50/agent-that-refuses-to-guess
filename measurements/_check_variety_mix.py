import os, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
# 이 폴더는 `measurements/` 다. 제품 코드는 한 단계 위에 있다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import load_day, filter_product
d = load_day("2026-08-28")
for kw in ["배추", "사과", "감자"]:
    m = filter_product(d.items, kw)
    print(f"\n=== '{kw}' 매칭 {len(m):,}건 ===")
    print("  품목명(gds_mclsf_nm):", dict(Counter((x.get('gds_mclsf_nm') or '').strip() for x in m).most_common(6)))
    print("  품종명(gds_sclsf_nm):", dict(Counter((x.get('gds_sclsf_nm') or '').strip() for x in m).most_common(6)))
# 춘천 vs 천안 배추가 무엇인지
print("\n=== 배추: 춘천 ↔ 천안 무엇을 팔았나 ===")
m = filter_product(d.items, "배추")
for mkt in ["춘천", "천안"]:
    sub = [x for x in m if (x.get("whsl_mrkt_nm") or "").strip() == mkt]
    c = Counter(f"{(x.get('gds_mclsf_nm') or '').strip()}/{(x.get('gds_sclsf_nm') or '').strip()}" for x in sub)
    print(f"  {mkt} ({len(sub)}건): {dict(c.most_common(4))}")
