"""profile_villa.py - 집계 결과(_rawdata/villa_*.json) 품질 프로파일: 거래 수·전세가율 분포·이상치"""
import collections, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAW = Path(__file__).parent.parent / "_rawdata"
bs = []
for f in RAW.glob("villa_*.json"):
    if f.name == "villa_meta.json":
        continue
    bs += json.loads(f.read_text(encoding="utf-8"))
print("건물", len(bs))
score = [b["n36"] + b["nr24"] for b in bs]
c = collections.Counter(min(s, 30) for s in score)
print("거래수(매매+전월세) 분포:", [(k, c[k]) for k in (3, 4, 5, 6, 8, 10, 15, 20, 30)])
print("거래수 상위 38,000번째 건물의 거래수:", sorted(score, reverse=True)[37999])
has_ratio = [b for b in bs if any(g["ratio"] > 0 for g in b["rg"])]
print("전세가율 계산 가능 건물:", len(has_ratio), f"({len(has_ratio) / len(bs):.0%})")
rs = sorted(g["ratio"] for b in has_ratio for g in b["rg"][:1] if g["ratio"] > 0)
q = lambda p: rs[int(len(rs) * p)]
print("전세가율 분위수 10/50/90/99:", q(.1), q(.5), q(.9), q(.99), "최대", rs[-1], "| >100%:", sum(1 for r in rs if r > 100))
by_kind = collections.Counter(b["kind"] for b in bs)
print("종류:", dict(by_kind))
noname = sum(1 for b in bs if b["name"].endswith("번지 빌라") or b["name"].endswith("번지 오피스텔"))
print("이름 대체(번지 빌라/오피스텔):", noname)
big = sorted(bs, key=lambda b: -(b["n36"] + b["nr24"]))[:5]
for b in big:
    print(" ", b["name"], b["doShort"], b["sigungu"], b["dong"], b["jibun"], b["n36"], b["nr24"])
