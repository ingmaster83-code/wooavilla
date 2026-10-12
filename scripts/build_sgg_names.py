#!/usr/bin/env python3
"""build_sgg_names.py - 시군구 법정동코드(앞 5자리) → (시도 약칭, 시군구명) 매핑을 우아아파트 데이터에서 만들어 scripts/sgg_names.json 에 저장한다.
(우아아파트 K-apt 단지의 bjdCode 앞 5자리와 시도·시군구명을 최빈값으로 연결 — wooaapt/scripts/process_trades.py 와 같은 방식)"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
RAW = ROOT.parent / "wooaapt" / "_rawdata"
detail = json.loads((RAW / "apt_detail.json").read_text(encoding="utf-8"))
apts = {}
for f in RAW.glob("apts_*.json"):
    for a in json.loads(f.read_text(encoding="utf-8")):
        apts[a["code"]] = a
cnt = defaultdict(Counter)
for code, d in detail.items():
    a = apts.get(code)
    if a and d.get("bjdCode"):
        cnt[d["bjdCode"][:5]][(a["doShort"], a["sigungu"])] += 1
names = {k: list(v.most_common(1)[0][0]) for k, v in cnt.items()}
codes = json.loads((ROOT / "scripts" / "sgg_codes.json").read_text(encoding="utf-8"))
missing = [c for c in codes if c not in names]
print(f"매핑 {len(names)}개 / 요청 시군구 {len(codes)}개 / 이름 없는 코드 {missing}")
(ROOT / "scripts" / "sgg_names.json").write_text(json.dumps(names, ensure_ascii=False, indent=0), encoding="utf-8")
