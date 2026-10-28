#!/usr/bin/env bash
# T15 sweep: lateral_sigma_m 0 / 0.10 / 0.15, interleaved per seed, plus the close same-clothes pair.
# Needs: docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:sweep .
# Usage: bash experiments/sim/scripts/run_lateral_sweep.sh <new_out_dir> [image]
# The out dir must be new: runs are never reused. Each run's [GATE] log line is checked against the
# requested lateral_sigma_m; a mismatch or a run without a score stops the sweep.
set -u
OUT=$(realpath -m "${1:?out dir}"); IMG=${2:-twin:sweep}
[ -e "$OUT" ] && { echo "out dir exists: $OUT"; exit 1; }
mkdir -p "$OUT"; docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/IMAGE_ID"
run() {  # tag scenario seed realism(0/1) lateral_sigma_m
  local R=""; [ "$4" = 1 ] && R=--realism
  docker run --rm -v "$OUT":/repo/sim_runs "$IMG" python3 -m sim.twin.run_scenario --scenario "$2" \
    --bridge-mode mps $R --ros-param lateral_sigma_m:=$5 --seed "$3" --out "sim_runs/$1" > "$OUT/$1.stdout" 2>&1
  local ok=0
  for d in "$OUT/$1"/*_mps; do
    [ -f "$d/score.json" ] || { echo "no score: $d"; exit 2; }
    grep -q "\[GATE\].*lateral_sigma_m=$(python3 -c "print(f'{float($5):g}')")\b" "$d/sync_fusion.log" \
      || { echo "gate setting not applied: $d"; exit 3; }
    ok=1
  done
  [ $ok = 1 ] || { echo "no run folder: $1"; exit 2; }
}
for sd in $(seq 8 27); do for ls in 0.0 0.10 0.15; do run "ss_${ls}_s$sd" side_step "$sd" 1 $ls; done; done
echo "side_step done $(date -u +%H:%MZ)"
for sd in $(seq 0 9); do for ls in 0.0 0.10 0.15; do run "cp_real_${ls}_s$sd" close_pair_same "$sd" 1 $ls; done; done
for sd in $(seq 0 4); do for ls in 0.0 0.10 0.15; do run "cp_clean_${ls}_s$sd" close_pair_same "$sd" 0 $ls; done; done
echo "close_pair done $(date -u +%H:%MZ)"
for sd in 0 1 2; do run "reg_identity_0.10_s$sd" identity "$sd" 1 0.10; done
for sd in $(seq 0 9); do run "zz_0.10_s$sd" zigzag "$sd" 1 0.10; done
echo "0.10 regressions done $(date -u +%H:%MZ)"
echo ALLDONE
