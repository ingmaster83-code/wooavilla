#!/bin/bash
# 월간 갱신: ① 확정 월 이력 보강(fill-hist) → ② 최근 2개월 재수집(recent) → ③ 건물 단위 집계(process_villa).
# 종류별 일일 호출 한도가 따로라 4종을 병렬로 받는다. 하나라도 실패하면 비정상 종료해 빌드·배포를 막는다(기존 배포 유지).
set -u
cd "$(dirname "$0")/.."
mkdir -p data
KINDS="rh_trade rh_rent offi_trade offi_rent"
declare -A PID
for k in $KINDS; do
  (
    python scripts/fetch_villa.py --kind "$k" --mode fill-hist &&
    python scripts/fetch_villa.py --kind "$k" --mode recent
  ) > "data/fetch_$k.log" 2>&1 &
  PID[$k]=$!
done
FAIL=0
for k in $KINDS; do
  wait "${PID[$k]}" || { echo "[$k] 수집 실패"; FAIL=1; }
  echo "=== $k ==="
  tail -n 6 "data/fetch_$k.log"
done
[ "$FAIL" = "0" ] || exit 1
python scripts/process_villa.py 3
