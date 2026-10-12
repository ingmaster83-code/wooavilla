"""빌드 결과(_site) 검증: 누출/태그 균형/중복 제목/사이트맵/검색 색인"""
import collections
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
root = sys.argv[1] if len(sys.argv) > 1 else "_site"
tl = collections.defaultdict(list)
bad = collections.Counter()
samples = {}
n = 0
for d, _, fs in os.walk(root):
    if "index.html" not in fs:
        continue
    p = os.path.join(d, "index.html").replace(os.sep, "/")
    s = open(p, encoding="utf-8").read()
    n += 1
    m = re.search(r"<title>(.*?)</title>", s, re.S)
    tl[m.group(1) if m else None].append(p)
    checks = {
        "leak": re.search(r"{{|{%|\bnil\b|undefined|NaN", s),
        "unbal": s.count("<div") != s.count("</div>") or s.count("<table") != s.count("</table>") or s.count("<details") != s.count("</details>"),
        "noh1": "<h1" not in s,
        "nodesc": 'meta name="description" content=""' in s,
    }
    for k, v in checks.items():
        if v:
            bad[k] += 1
            samples.setdefault(k, p)
print("pages", n, dict(bad), samples)
dups = [(t, ps) for t, ps in tl.items() if len(ps) > 1]
print("dup titles", len(dups), sum(len(ps) for _, ps in dups))
for t, ps in dups[:6]:
    print(" ", t, [x.split("/")[-2] for x in ps])
for f in sorted(glob.glob(root + "/sitemap*.xml")):
    print(f, os.path.getsize(f), open(f, encoding="utf-8").read().count("<loc>"))
idx = json.load(open(root + "/search_index.json", encoding="utf-8"))
print("search idx", len(idx), idx[0], idx[-1])
