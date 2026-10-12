#!/usr/bin/env python3
"""
fetch_villa.py - 국토교통부 연립다세대·오피스텔 실거래(매매·전월세) API를 시군구×월 단위로 수집해 data/cache/ 에 캐시한다.

종류(kind): rh_trade(연립다세대 매매) rh_rent(연립다세대 전월세) offi_trade(오피스텔 매매) offi_rent(오피스텔 전월세)
- 이미 받은 (종류, 월, 시군구)는 건너뛴다. 최근 2개월은 신고 지연·해제 때문에 --refresh-recent 일 때만 다시 받는다.
- 일일 호출 한도(API별 10,000회)에 걸리면 정상 종료하고 다음 실행에서 이어서 받는다. 종류별로 따로 프로세스를 띄우면 한도가 따로 적용된다.
사용: python scripts/fetch_villa.py --kind rh_trade [--months 36] [--workers 3] [--max-calls 9500] [--refresh-recent]
키: 환경변수 DATA_GO_KR_API_KEY (없으면 ../hosppass/.env 의 API_KEY — 로컬 전용)
"""
import argparse, json, os, sys, threading, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
CACHE = ROOT / "data" / "cache"
SGG = json.loads((ROOT / "scripts" / "sgg_codes.json").read_text(encoding="utf-8"))
RECENT_N = 2
ROWS = 1000

BASE = "https://apis.data.go.kr/1613000/"
URLS = {
    "rh_trade": BASE + "RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
    "rh_rent": BASE + "RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "offi_trade": BASE + "RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
    "offi_rent": BASE + "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
}
NAME_TAG = {"rh_trade": "mhouseNm", "rh_rent": "mhouseNm", "offi_trade": "offiNm", "offi_rent": "offiNm"}
DEFAULT_MONTHS = {"rh_trade": 36, "rh_rent": 24, "offi_trade": 36, "offi_rent": 24}


def get_key():
    k = os.environ.get("DATA_GO_KR_API_KEY")
    if k:
        return k
    env = ROOT.parent / "hosppass" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("DATA_GO_KR_API_KEY 가 없습니다.")


KEY = get_key()
sess = requests.Session()
HTTP = [0]


class QuotaExceeded(Exception):
    pass


MIN_GAP = 0.6                 # 프로세스 전체 호출 간격(초) — 초당 요청 제한(코드 23) 회피
_gate = threading.Lock()
_next_at = [0.0]


def throttle(extra=0.0):
    """모든 스레드가 공유하는 호출 간격 제어. extra>0 이면 그만큼 전체를 멈춘다(초당 제한에 걸린 뒤 냉각)."""
    with _gate:
        now = time.time()
        if extra:
            _next_at[0] = max(_next_at[0], now + extra)
        wait = _next_at[0] - now
        _next_at[0] = max(_next_at[0], now) + MIN_GAP
    if wait > 0:
        time.sleep(wait)


def txt(it, tag):
    e = it.find(tag)
    return (e.text or "").strip() if e is not None and e.text else ""


def num(s, f=float):
    try:
        return f(str(s).replace(",", "").strip())
    except ValueError:
        return 0


def parse_items(root, kind):
    rows = []
    name_tag = NAME_TAG[kind]
    for it in root.iter("item"):
        ymd = num(txt(it, "dealYear"), int) * 10000 + num(txt(it, "dealMonth"), int) * 100 + num(txt(it, "dealDay"), int)
        base = [txt(it, name_tag), txt(it, "umdNm"), txt(it, "jibun"), ymd, num(txt(it, "excluUseAr")), num(txt(it, "floor"), int)]
        htype = txt(it, "houseType")[:2]
        if kind.endswith("_trade"):
            cancelled = 1 if txt(it, "cdealType") == "O" or txt(it, "cdealDay") else 0
            base += [num(txt(it, "dealAmount"), int), num(txt(it, "buildYear"), int), cancelled, txt(it, "dealingGbn")[:2], htype]
        else:
            base += [num(txt(it, "deposit"), int), num(txt(it, "monthlyRent"), int), txt(it, "contractType")[:2], num(txt(it, "buildYear"), int), htype, txt(it, "useRRRight")[:2]]
        rows.append(base)
    return rows


def fetch_one(kind, sgg, ym):
    rows, page = [], 1
    while True:
        for attempt in range(8):
            try:
                throttle()
                HTTP[0] += 1
                r = sess.get(URLS[kind], params={"serviceKey": KEY, "LAWD_CD": sgg, "DEAL_YMD": ym, "numOfRows": ROWS, "pageNo": page}, timeout=(15, 45))
                if "PER_SECOND" in r.text:
                    throttle(extra=15)          # 초당 제한: 일일 한도가 아니므로 쉬었다가 다시 시도
                    raise RuntimeError("per-second limit")
                if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in r.text:
                    raise QuotaExceeded()       # 일일 한도
                if r.status_code == 429:
                    throttle(extra=15)
                    raise RuntimeError("HTTP 429")
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                root = ET.fromstring(r.text)
                code = (root.findtext(".//resultCode") or "").strip()
                if code not in ("000", "00"):
                    msg = root.findtext(".//resultMsg") or r.text[:100]
                    if "LIMIT" in msg.upper():
                        raise QuotaExceeded()
                    raise RuntimeError(f"resultCode {code}: {msg}")
                break
            except QuotaExceeded:
                raise
            except Exception as e:
                if attempt == 7:
                    raise
                time.sleep(3 * (attempt + 1))
        batch = parse_items(root, kind)
        rows.extend(batch)
        total = num(root.findtext(".//totalCount") or "0", int)
        if len(rows) >= total or not batch:
            return rows
        page += 1
        time.sleep(0.05)


def months_back(n):
    t = date.today()
    y, m = t.year, t.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(URLS))
    ap.add_argument("--months", type=int, default=0)
    ap.add_argument("--max-calls", type=int, default=9500)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--refresh-recent", action="store_true")
    args = ap.parse_args()
    kind = args.kind
    months = months_back(args.months or DEFAULT_MONTHS[kind])
    recent = set(months[:RECENT_N]) if args.refresh_recent else set()
    done = skipped = 0
    for ym in months:
        d = CACHE / kind / ym
        d.mkdir(parents=True, exist_ok=True)
        todo = [g for g in SGG if ym in recent or not (d / f"{g}.json").exists()]
        skipped += len(SGG) - len(todo)
        if not todo:
            continue
        if HTTP[0] >= args.max_calls:
            print(f"호출 {HTTP[0]}회 도달 — 중단(다음 실행에서 이어서). 받음 {done}, 건너뜀 {skipped}", flush=True)
            sys.exit(0)
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                results = list(ex.map(lambda g: (g, fetch_one(kind, g, ym)), todo))
        except QuotaExceeded:
            print(f"일일 호출 한도 도달(HTTP {HTTP[0]}회) — 중단(다음 실행에서 이어서). 받음 {done}, 건너뜀 {skipped}", flush=True)
            sys.exit(0)
        done += len(results)
        for g, rows in results:
            (d / f"{g}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[{kind}] {ym} {len(results)}개 시군구 (HTTP {HTTP[0]})", flush=True)
    print(f"완료: 받음 {done}, 건너뜀 {skipped}", flush=True)


if __name__ == "__main__":
    main()
