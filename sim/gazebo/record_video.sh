#!/usr/bin/env bash
# Record the Gazebo window of one scenario to MP4 on a headless Linux host (or WSL2).
#   sim/gazebo/record_video.sh SCENARIO [BRIDGE_MODE] [OUT_DIR]
# Needs: Docker, Xvfb, ffmpeg on the host, and the image built from sim/docker/Dockerfile.gazebo.
# With a real display (Linux desktop, WSLg) you can instead run run_gazebo.py --gui directly.
set -Eeuo pipefail
SC=${1:?scenario}; BR=${2:-current}; OUT=$(realpath -m "${3:-sim_runs}")
mkdir -p "$OUT"
DISP=:$((90 + RANDOM % 9))
Xvfb "$DISP" -screen 0 1280x720x24 -nolisten tcp >/dev/null 2>&1 &
XPID=$!
trap 'kill $XPID 2>/dev/null || true' EXIT
sleep 2
docker run --rm -e DISPLAY="$DISP" -v /tmp/.X11-unix:/tmp/.X11-unix -v "$OUT":/repo/sim_runs \
  following-robot-twin-gz python3 -m sim.gazebo.run_gazebo --scenario "$SC" --bridge-mode "$BR" \
  --gui --out /repo/sim_runs > "$OUT/run_${SC}_${BR}.txt" 2>&1 &
DPID=$!
sleep 10  # Gazebo start-up; recording starts just before the scenario does
LABEL="Offline twin (Gazebo) - scenario ${SC}, bridge ${BR} - simulation, not robot data"
ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -video_size 1280x720 -framerate 15 -i "$DISP" \
  -vf "drawtext=text='${LABEL}':x=20:y=h-40:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8" \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p "$OUT/${SC}_${BR}.mp4" &
FPID=$!
wait $DPID
kill -INT $FPID; wait $FPID 2>/dev/null || true
echo "video: $OUT/${SC}_${BR}.mp4"
