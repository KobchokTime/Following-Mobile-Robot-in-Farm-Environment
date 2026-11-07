#!/usr/bin/env bash
# Twin runs for the lateral-distance gate (experiments/sim/2026-10-28_lateral_gate.md), one at a time.
# Needs the image: docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:lateral .
# Usage: bash experiments/sim/scripts/run_lateral_gate.sh <out_dir> [image]
set -u
OUT=$(realpath -m "${1:?out dir}"); IMG=${2:-twin:lateral}; mkdir -p "$OUT"
run() {  # tag scenario seed realism(0/1) lateral_sigma_m [extra NAME:=VALUE ...]
  local tag=$1 sc=$2 sd=$3 R="" ls=$5; [ "$4" = 1 ] && R=--realism; shift 5
  local extra=(); for p in "$@"; do extra+=(--ros-param "$p"); done
  [ -f "$OUT/$tag/summary.json" ] && return  # resumable: finished runs are skipped
  docker run --rm -v "$OUT":/repo/sim_runs "$IMG" python3 -m sim.twin.run_scenario --scenario "$sc" \
    --bridge-mode mps $R --ros-param lateral_sigma_m:=$ls "${extra[@]}" --seed "$sd" --out "sim_runs/$tag" > /dev/null 2>&1
}
for sd in $(seq 8 27); do
  run "ss_on_s$sd" side_step "$sd" 1 0.15; run "ss_off_s$sd" side_step "$sd" 1 0.0
done; echo "side_step done $(date -u +%H:%MZ)"
for sd in 0 1 2; do run "reg_identity_s$sd" identity "$sd" 1 0.15; run "reg_solo_s$sd" solo "$sd" 1 0.15; done
echo "identity/solo done $(date -u +%H:%MZ)"
for sd in $(seq 0 9); do
  run "col_shade_crossing_s$sd" shade_crossing "$sd" 1 0.15
  run "col_shade_side_by_side_s$sd" shade_side_by_side "$sd" 1 0.15
  run "look_clean_s$sd" lookalike_after_loss "$sd" 0 0.15
  run "look_real_s$sd" lookalike_after_loss "$sd" 1 0.15
done; echo "colour done $(date -u +%H:%MZ)"
# T13 correction: the re-acquisition distance rule really off (these parameters are now declared)
OFF=(reacquire_dist_m:=100.0 reacquire_dist_max_m:=100.0)
for sd in $(seq 0 9); do
  run "look_ruleoff_clean_s$sd" lookalike_after_loss "$sd" 0 0.15 "${OFF[@]}"
  run "look_ruleoff_real_s$sd" lookalike_after_loss "$sd" 1 0.15 "${OFF[@]}"
done; echo "rule-off done $(date -u +%H:%MZ)"
# zigzag check: solo s0-2 with 0.15 failed zigzag 3/3, so compare on vs off interleaved
for sd in $(seq 0 9); do
  run "zz_on_s$sd" zigzag "$sd" 1 0.15; run "zz_off_s$sd" zigzag "$sd" 1 0.0
done; echo "zigzag done $(date -u +%H:%MZ)"
echo ALLDONE
