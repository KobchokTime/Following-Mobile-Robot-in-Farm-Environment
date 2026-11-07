#!/usr/bin/env bash
# Every twin scenario with realism, seeds S0..S1 (default 0-4), one run at a time, on one image.
# Shows which scenarios still fail before a fix (the "twin at 100%" check).
# Needs: docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t <image> .
# Usage: bash experiments/sim/scripts/run_baseline.sh <new_out_dir> <image> [first_seed] [last_seed] [ros-param ...]
set -u
OUT=$(realpath -m "${1:?out dir}"); IMG=${2:?image}; S0=${3:-0}; S1=${4:-4}; shift 4 2>/dev/null || shift $#
[ -e "$OUT" ] && { echo "out dir exists: $OUT"; exit 1; }
mkdir -p "$OUT"; docker image inspect "$IMG" --format '{{.Id}}' > "$OUT/IMAGE_ID"
P=(); for p in "$@"; do P+=(--ros-param "$p"); done
SCEN=$(docker run --rm "$IMG" python3 -c "from sim.twin.scenarios import SCENARIO_LOOKUP as L; print(' '.join(sorted(L)))")
for sd in $(seq "$S0" "$S1"); do for sc in $SCEN; do
  docker run --rm -v "$OUT":/repo/sim_runs "$IMG" python3 -m sim.twin.run_scenario --scenario "$sc" \
    --bridge-mode mps --realism "${P[@]}" --seed "$sd" --out "sim_runs/${sc}_s$sd" > "$OUT/${sc}_s$sd.stdout" 2>&1
  [ -f "$OUT/${sc}_s$sd/${sc}_mps/score.json" ] || { echo "no score: ${sc}_s$sd"; exit 2; }
done; echo "seed $sd done $(date -u +%H:%MZ)"; done
echo ALLDONE
