import json, sys, glob, collections
sys.stdout.reconfigure(encoding="utf-8")
base = "C:/개인/wooahouse/wooavilla/data/cache"
for kind in ("rh_trade", "rh_rent", "offi_trade", "offi_rent"):
    files = glob.glob(f"{base}/{kind}/*/*.json")
    rows = []
    for f in files:
        rows += json.load(open(f, encoding="utf-8"))
    names = collections.Counter(r[0] for r in rows)
    empty = sum(1 for r in rows if not r[0] or r[0] in ("-", "연립", "다세대"))
    jib_empty = sum(1 for r in rows if not r[2])
    print(f"{kind}: files {len(files)}, rows {len(rows)}, empty/junk name {empty}, no jibun {jib_empty}")
    print("  top names:", names.most_common(6))
    print("  sample:", rows[:2])
    if kind.startswith("rh"):
        print("  htype:", collections.Counter((r[-1] if kind.endswith("trade") else r[-2]) for r in rows).most_common(4))
