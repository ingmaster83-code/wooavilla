#!/usr/bin/env python3
"""
process_villa.py - data/cache/{rh_trade,rh_rent,offi_trade,offi_rent}/ 의 원자료를 건물(시군구+법정동+지번)별로 집계해
_rawdata/villa_{시도}.json 과 _rawdata/villa_meta.json 을 만든다.

캐시 행 형식
  trade: [이름, 법정동, 지번, ymd, 전용㎡, 층, 금액(만원), 준공연도, 해제(0/1), 거래유형, 주택유형]
  rent : [이름, 법정동, 지번, ymd, 전용㎡, 층, 보증금, 월세, 계약구분, 준공연도, 주택유형, 갱신요구권]

출력 레코드(건물 1건)
  id, kind('v' 빌라 | 'o' 오피스텔), slug, name, doShort, sigungu, dong, jibun, by, ht(연립|다세대|오피스텔),
  n36(36개월 매매), n24(24개월 매매), nr24(24개월 전월세), last(마지막 거래일),
  tg: 평형(전용 정수㎡)별 매매 [{a, py, n36, avg36, min36, max36, maxd, last:[ymd,floor,amt], n24, avg24}]
  rg: 평형별 전월세 [{a, nj, avgj, nw, avgwd, avgwm, ratio}]  ratio = 24개월 평균 전세 / 24개월 평균 매매 (%)
  t: 최근 매매 [[ymd, 전용, 층, 금액]], r: 최근 전월세 [[ymd, 전용, 층, 보증금, 월세, 구분]],
  yr: 최다 거래 평형의 연도별 [[year, n, avg]]
"""
import hashlib, json, re, sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
CACHE = ROOT / "data" / "cache"
RAW = ROOT / "_rawdata"
TODAY = date.today()
SGG = json.loads((ROOT / "scripts" / "sgg_names.json").read_text(encoding="utf-8"))

MIN_TX = int(sys.argv[1]) if len(sys.argv) > 1 else 3   # 36개월 매매 + 24개월 전월세 합계가 이보다 적으면 페이지를 만들지 않는다
MIN_TOTAL = 20000


def ymd_of(d):
    return d.year * 10000 + d.month * 100 + d.day


Y24 = ymd_of(TODAY - timedelta(days=730))
Y36 = ymd_of(TODAY - timedelta(days=1095))
JUNK = re.compile(r"^[\(\)\d\-\s,.~]*$")
HT = {"연립": "연립", "다세": "다세대"}


def clean_name(s):
    s = re.sub(r"\(\s*[\d\-\s,.]*\)", "", s or "")        # 지번만 들어간 괄호 제거: 꿈꾸지오(268-9) → 꿈꾸지오
    s = re.sub(r"\s+", " ", s).strip()
    return "" if JUNK.match(s) else s


def py_label(a):
    """전용면적(㎡) → 공급 평형 근사(전용×1.32÷3.3058). 빌라·오피스텔은 전용률이 낮아 아파트보다 근사 오차가 크다."""
    return int(round(a * 1.32 / 3.3058))


def dedupe(rows, idx):
    seen, out = set(), []
    for r in rows:
        k = tuple(r[i] for i in idx)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def load(kind):
    out = defaultdict(list)     # (sgg, dong, jibun) -> rows
    base = CACHE / kind
    if not base.exists():
        return out
    for mdir in sorted(base.iterdir()):
        for f in mdir.glob("*.json"):
            sgg = f.stem
            for r in json.loads(f.read_text(encoding="utf-8")):
                if r[1] and r[2]:
                    out[(sgg, r[1], r[2])].append(r)
    return out


def trade_groups(rows):
    by = defaultdict(list)
    for r in rows:
        by[int(round(r[4]))].append(r)
    groups = []
    for a, lst in by.items():
        if a <= 0:
            continue
        lst.sort(key=lambda x: (x[3], x[5]))
        l24 = [x for x in lst if x[3] >= Y24]
        mx = max(lst, key=lambda x: (x[6], x[3]))
        last = lst[-1]
        groups.append({"a": a, "py": py_label(a), "n36": len(lst), "avg36": int(sum(x[6] for x in lst) / len(lst)), "min36": min(x[6] for x in lst), "max36": mx[6],
                       "maxd": mx[3], "last": [last[3], last[5], last[6]], "n24": len(l24), "avg24": int(sum(x[6] for x in l24) / len(l24)) if l24 else 0})
    groups.sort(key=lambda g: (-g["n36"], g["a"]))
    return groups[:6]


def rent_groups(rows, tg):
    by = defaultdict(list)
    for r in rows:
        by[int(round(r[4]))].append(r)
    t24 = {g["a"]: g["avg24"] for g in tg}
    out = []
    for a, lst in by.items():
        if a <= 0:
            continue
        j = [x[6] for x in lst if x[7] == 0]
        w = [x for x in lst if x[7] > 0]
        avgj = int(sum(j) / len(j)) if j else 0
        ratio = round(avgj / t24[a] * 100) if avgj and t24.get(a) else 0
        out.append({"a": a, "nj": len(j), "avgj": avgj, "nw": len(w),
                    "avgwd": int(sum(x[6] for x in w) / len(w)) if w else 0, "avgwm": int(sum(x[7] for x in w) / len(w)) if w else 0, "ratio": ratio})
    out.sort(key=lambda g: (-(g["nj"] + g["nw"]), g["a"]))
    return out[:6]


def make_rec(kcode, key, t_all, r_all, stat):
    sgg, dong, jibun = key
    do, sg = SGG[sgg]
    t_rows = dedupe([r for r in t_all if not r[8] and r[6] > 0 and r[3] >= Y36], (3, 4, 5, 6))
    r_rows = dedupe([r for r in r_all if r[3] >= Y24 and (r[6] > 0 or r[7] > 0)], (3, 4, 5, 6, 7))
    if len(t_rows) + len(r_rows) < MIN_TX:
        stat["skip_small"] += 1
        return None
    names = Counter(clean_name(r[0]) for r in t_rows + r_rows)
    names.pop("", None)
    name = names.most_common(1)[0][0] if names else ""
    if not name:
        name = f"{dong} {jibun}번지 " + ("오피스텔" if kcode == "o" else "빌라")
        stat["name_fallback"] += 1
    if kcode == "v":
        hts = Counter(HT.get(r[10], "") for r in t_rows) + Counter(HT.get(r[10], "") for r in r_rows)
        hts.pop("", None)
        ht = hts.most_common(1)[0][0] if hts else "다세대"
    else:
        ht = "오피스텔"
    bys = Counter([r[7] for r in t_rows if r[7]] + [r[9] for r in r_rows if r[9]])
    by = bys.most_common(1)[0][0] if bys else 0
    t_sorted = sorted(t_rows, key=lambda x: (x[3], x[5]), reverse=True)
    r_sorted = sorted(r_rows, key=lambda x: (x[3], x[5]), reverse=True)
    tg = trade_groups(t_rows)
    rg = rent_groups(r_rows, tg)
    yr = []
    if tg:
        ys = defaultdict(list)
        for r in t_rows:
            if int(round(r[4])) == tg[0]["a"]:
                ys[r[3] // 10000].append(r[6])
        yr = [[y, len(v), int(sum(v) / len(v))] for y, v in sorted(ys.items())]
    slug_name = re.sub(r"[^\w가-힣]+", "-", name).strip("-")[:20] or "b"
    h = hashlib.md5(f"{kcode}|{sgg}|{dong}|{jibun}".encode()).hexdigest()[:6]
    return {
        "id": f"{kcode}{sgg}{h}", "kind": kcode, "slug": f"{slug_name}-{sgg}-{h}", "name": name, "doShort": do, "sigungu": sg, "dong": dong, "jibun": jibun,
        "by": by, "ht": ht, "n36": len(t_rows), "n24": sum(1 for r in t_rows if r[3] >= Y24), "nr24": len(r_rows),
        "last": max([r[3] for r in t_rows + r_rows]),
        "tg": tg, "rg": rg,
        "t": [[r[3], round(r[4], 1), r[5], r[6]] for r in t_sorted[:15]],
        "r": [[r[3], round(r[4], 1), r[5], r[6], r[7], r[8]] for r in r_sorted[:12]],
        "yr": yr,
    }


def main():
    out_by_do = defaultdict(list)
    stat = Counter()
    v_t, v_r, o_t, o_r = load("rh_trade"), load("rh_rent"), load("offi_trade"), load("offi_rent")
    v_keys, o_keys = set(v_t) | set(v_r), set(o_t) | set(o_r)
    print(f"건물 후보 빌라 {len(v_keys):,} / 오피스텔 {len(o_keys):,} / 양쪽 자료에 모두 있는 지번 {len(v_keys & o_keys):,}", flush=True)

    def name_of(rows):
        c = Counter(clean_name(r[0]) for r in rows)
        c.pop("", None)
        return c.most_common(1)[0][0] if c else ""

    for key in v_keys | o_keys:
        if key[0] not in SGG:
            stat["no_sgg"] += 1
            continue
        in_v, in_o = key in v_keys, key in o_keys
        vt, vr, ot, orr = v_t.get(key, []), v_r.get(key, []), o_t.get(key, []), o_r.get(key, [])
        if in_v and in_o:
            nv, no = name_of(vt + vr), name_of(ot + orr)
            same = (not nv) or (not no) or nv == no or nv in no or no in nv
            if same:      # 같은 건물이 연립다세대·오피스텔 자료에 모두 올라온 경우: 한 건물로 합치고, 거래가 더 많은 쪽 종류를 따른다
                kcode = "o" if len(ot) + len(orr) >= len(vt) + len(vr) else "v"
                rec = make_rec(kcode, key, vt + ot, vr + orr, stat)
                stat["merged"] += 1
                if rec:
                    out_by_do[rec["doShort"]].append(rec)
                    stat["ok_" + kcode] += 1
                continue
        for kcode, tt, rr, present in (("v", vt, vr, in_v), ("o", ot, orr, in_o)):
            if not present:
                continue
            rec = make_rec(kcode, key, tt, rr, stat)
            if rec:
                out_by_do[rec["doShort"]].append(rec)
                stat["ok_" + kcode] += 1

    for old in RAW.glob("villa_*.json"):
        old.unlink()
    RAW.mkdir(exist_ok=True)
    total = 0
    for do, lst in out_by_do.items():
        lst.sort(key=lambda r: (r["sigungu"], r["dong"], r["name"], r["jibun"]))
        (RAW / f"villa_{do}.json").write_text(json.dumps(lst, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        total += len(lst)
    latest = max((r["last"] for lst in out_by_do.values() for r in lst), default=0)
    (RAW / "villa_meta.json").write_text(json.dumps({"latest": latest, "built": ymd_of(TODAY), "min_tx": MIN_TX}), encoding="utf-8")
    sz = sum(f.stat().st_size for f in RAW.glob("villa_*.json")) / 1e6
    print(f"건물 레코드 {total:,} (빌라 {stat['ok_v']:,}, 오피스텔 {stat['ok_o']:,}) / 제외(거래 적음) {stat['skip_small']:,} / 이름 대체 {stat['name_fallback']:,} / 종류 중복 병합 {stat['merged']:,} / 지역 없음 {stat['no_sgg']:,} / {sz:.1f}MB / 최근 거래일 {latest}")
    if total < MIN_TOTAL and "--partial" not in sys.argv:
        print(f"※ 건물이 {MIN_TOTAL:,}건 미만입니다(수집이 끝나지 않았다면 정상).")


if __name__ == "__main__":
    main()
