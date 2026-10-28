#!/usr/bin/env bash
# T15 follow-up: a stranger steps out beside the target (walk_up_same); the scan tells the gate.
# Variants, interleaved per seed:
#   old    lateral_sigma_m 0 (the gate before T15)
#   noscan lateral_sigma_m 0.15, crowd_from_scan false (T15 round 2 as merged)
#   scan   lateral_sigma_m 0.15, crowd_from_scan true (the new default)
# Needs: docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:walkup .
3]|3] bash experiments/sim/scripts/run_walk_up.sh <new_out_dir> [image]
# Round 1 ran at cd6eead, where the radius was fixed at 1.0 (CROWD_RADIUS=1.0 on a later build repeats it).
set -u
OUT=$(realpath -m "${1:?out dir}"); IMG=${2:-twin:walkup}
[ -e "$OUT" ] && { echo "out dir exists: $OUT"; exit 1; }
mkdir -p "$OUT"; docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/IMAGE_ID"
params() { case $1 in
  old) echo "lateral_sigma_m:=0.0 crowd_from_scan:=true" ;;
  noscan) echo "lateral_sigma_m:=0.15 crowd_from_scan:=false" ;;
  scan) echo "lateral_sigma_m:=0.15 crowd_from_scan:=true crowd_radius_m:=${CROWD_RADIUS:-0.5}" ;;
esac; }
run() {  # tag scenario seed realism(0/1) variant
  local R=""; [ "$4" = 1 ] && R=--realism
  local P=(); for p in $(params "$5"); do P+=(--ros-param "$p"); done
  docker run --rm -v "$OUT":/repo/sim_runs "$IMG" python3 -m sim.twin.run_scenario --scenario "$2" \
    --bridge-mode mps $R "${P[@]}" --seed "$3" --out "sim_runs/$1" > "$OUT/$1.stdout" 2>&1
  local ok=0
  for d in "$OUT/$1"/*_mps; do
    [ -f "$d/score.json" ] || { echo "no score: $d"; exit 2; }
    for p in $(params "$5"); do
      local k=${p%%:=*} v=${p##*:=}
      case $v in true) v=1 ;; false) v=0 ;; *) v=$(python3 -c "print(f'{float(\"$v\"):g}')") ;; esac
      grep -qE "\[GATE\].* $k=${v//./\\.}( |\$)" "$d/sync_fusion.log" || { echo "gate setting not applied ($k=$v): $d"; exit 3; }
    done
    ok=1
  done
  [ $ok = 1 ] || { echo "no run folder: $1"; exit 2; }
}
if [ "${ROUND:-1}" != 1 ]; then  # round 2 (1be3357): crowd_radius_m 0.5; round 3 (0d74732): also only boxes near the prediction; round 4 (later): spread rule
  for sd in $(seq 8 27); do for v in noscan scan; do run "ss_${v}_s$sd" side_step "$sd" 1 $v; done; done
  for sd in $(seq 0 9); do run "wu_real_scan_s$sd" walk_up_same "$sd" 1 scan; done
  for sd in $(seq 0 4); do run "cp_real_scan_s$sd" close_pair_same "$sd" 1 scan; done
  echo ALLDONE; exit 0
fi
for sd in $(seq 0 9); do for v in old noscan scan; do run "wu_real_${v}_s$sd" walk_up_same "$sd" 1 $v; done; done
echo "walk_up done $(date -u +%H:%MZ)"
for sd in $(seq 8 17); do for v in noscan scan; do run "ss_${v}_s$sd" side_step "$sd" 1 $v; done; done
for sd in $(seq 0 4); do run "cp_real_scan_s$sd" close_pair_same "$sd" 1 scan; done
echo ALLDONE
