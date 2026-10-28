#!/usr/bin/env bash
# T15 round 2b: lateral gate with the ambiguity check, against the old gate and the floor without it.
# Variants, interleaved per seed:
#   old   lateral_sigma_m 0
#   amb   lateral_sigma_m 0.15, ambiguity_radius_m 1 (the new default)
#   floor lateral_sigma_m 0.15, ambiguity_radius_m 0 (round 1: no ambiguity check)
# Needs: docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:amb .
# Usage: bash experiments/sim/scripts/run_ambiguity_sweep.sh <new_out_dir> [image]
# CONFIRM=1 runs only the round-2c confirmation (old vs amb: close_pair_same and side_step s8-17).
set -u
OUT=$(realpath -m "${1:?out dir}"); IMG=${2:-twin:amb}
[ -e "$OUT" ] && { echo "out dir exists: $OUT"; exit 1; }
mkdir -p "$OUT"; docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/IMAGE_ID"
params() { case $1 in
  old) echo "lateral_sigma_m:=0.0 ambiguity_radius_m:=1.0" ;;
  amb) echo "lateral_sigma_m:=0.15 ambiguity_radius_m:=1.0" ;;
  floor) echo "lateral_sigma_m:=0.15 ambiguity_radius_m:=0.0" ;;
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
      local k=${p%%:=*} v=$(python3 -c "print(f'{float(\"${p##*:=}\"):g}')")
      grep -q "\[GATE\].*\b$k=$v\b" "$d/sync_fusion.log" || { echo "gate setting not applied ($k=$v): $d"; exit 3; }
    done
    ok=1
  done
  [ $ok = 1 ] || { echo "no run folder: $1"; exit 2; }
}
if [ "${CONFIRM:-0}" = 1 ]; then  # round 2c: after the lock-on fix, old vs amb only
  for sd in $(seq 0 9); do for v in old amb; do run "cp_real_${v}_s$sd" close_pair_same "$sd" 1 $v; done; done
  for sd in $(seq 0 4); do for v in old amb; do run "cp_clean_${v}_s$sd" close_pair_same "$sd" 0 $v; done; done
  for sd in $(seq 8 17); do for v in old amb; do run "ss_${v}_s$sd" side_step "$sd" 1 $v; done; done
  echo ALLDONE; exit 0
fi
for sd in $(seq 8 27); do for v in old amb floor; do run "ss_${v}_s$sd" side_step "$sd" 1 $v; done; done
echo "side_step done $(date -u +%H:%MZ)"
for sd in $(seq 0 9); do for v in old amb floor; do run "cp_real_${v}_s$sd" close_pair_same "$sd" 1 $v; done; done
for sd in $(seq 0 4); do for v in old amb floor; do run "cp_clean_${v}_s$sd" close_pair_same "$sd" 0 $v; done; done
echo "close_pair done $(date -u +%H:%MZ)"
for sd in 0 1 2; do run "reg_identity_amb_s$sd" identity "$sd" 1 amb; done
for sd in $(seq 0 9); do run "zz_amb_s$sd" zigzag "$sd" 1 amb; done
echo "amb regressions done $(date -u +%H:%MZ)"
echo ALLDONE
