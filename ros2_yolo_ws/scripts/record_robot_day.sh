#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: record_robot_day.sh --scenario LABEL [--output-root DIRECTORY] [--countdown SEC] [--duration SEC]

Record every currently available ROS 2 topic to an MCAP rosbag2 and save
tracked project configuration plus run metadata beside the bag.

Options:
  --scenario LABEL       Required short label using letters, digits, dot, _ or -
  --output-root DIR      Destination directory (default: ~/robot_day_recordings)
  --countdown SEC        Wait SEC seconds before recording, so one person can walk to the mark
  --duration SEC         Stop recording by itself after SEC seconds (no Ctrl-C needed)
  -h, --help             Show this help

Stop recording with Ctrl-C. The ROS 2 MCAP storage plugin must be installed.
Run from a clean checkout after recording the code commit you intend to test.
EOF
}

scenario=""
output_root="${ROBOT_DAY_OUTPUT:-$HOME/robot_day_recordings}"
countdown=0
duration=0

while (($#)); do
    case "$1" in
        --scenario)
            (($# >= 2)) || { usage >&2; exit 2; }
            scenario="$2"
            shift 2
            ;;
        --output-root)
            (($# >= 2)) || { usage >&2; exit 2; }
            output_root="$2"
            shift 2
            ;;
        --countdown|--duration)
            (($# >= 2)) && [[ "$2" =~ ^[0-9]+$ ]] || { usage >&2; exit 2; }
            if [[ "$1" == --countdown ]]; then countdown="$2"; else duration="$2"; fi
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! "$scenario" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    printf 'A valid --scenario label is required.\n' >&2
    usage >&2
    exit 2
fi

command -v ros2 >/dev/null || { printf 'ros2 is not on PATH. Source the ROS 2 setup first.\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'python3 is required for the run manifest.\n' >&2; exit 1; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir/../.." rev-parse --show-toplevel)"
commit_sha="$(git -C "$repo_root" rev-parse HEAD)"
git_branch="$(git -C "$repo_root" branch --show-current)"
git_dirty="$(git -C "$repo_root" status --porcelain | wc -l | tr -d ' ')"
started_at_utc="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
session_name="$(date -u +'%Y%m%dT%H%M%SZ')_${scenario}"
session_dir="$output_root/$session_name"

mkdir -p -- "$session_dir/config"
mapfile -d '' -t config_files < <(git -C "$repo_root" ls-files -z -- config ros2_yolo_ws/config)
copied_configs=()
for relative_path in "${config_files[@]}"; do
    lower_name="${relative_path,,}"
    case "$lower_name" in
        *.env|*.key|*.pem|*.p12|*secret*|*credential*)
            printf 'Skipping credential-like path: %s\n' "$relative_path" >&2
            continue
            ;;
    esac
    source_path="$repo_root/$relative_path"
    [[ -f "$source_path" ]] || continue
    mkdir -p -- "$session_dir/config/$(dirname -- "$relative_path")"
    cp -- "$source_path" "$session_dir/config/$relative_path"
    copied_configs+=("$relative_path")
done

manifest="$session_dir/recording.json"
python3 - "$manifest" "$scenario" "$commit_sha" "$git_branch" "${ROS_DISTRO:-unknown}" \
    "$started_at_utc" "$git_dirty" "${copied_configs[@]}" <<'PY'
import hashlib
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
scenario, commit, branch, ros_distro, started, dirty = sys.argv[2:8]
config_paths = sys.argv[8:]
config_entries = []
for relative in config_paths:
    copied = manifest_path.parent / "config" / relative
    digest = hashlib.sha256(copied.read_bytes()).hexdigest()
    config_entries.append({"path": relative, "sha256": digest})

manifest = {
    "scenario": scenario,
    "commit_sha": commit,
    "git_branch": branch,
    "git_dirty_file_count": int(dirty),
    "ros_distro": ros_distro,
    "started_at_utc": started,
    "ended_at_utc": None,
    "recorded_topics": "all topics available when rosbag2 starts",
    "storage_id": "mcap",
    "config": config_entries,
    "exit_code": None,
}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY

finish() {
    local result=$?
    trap - EXIT
    python3 - "$manifest" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$result" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["ended_at_utc"] = sys.argv[2]
data["exit_code"] = int(sys.argv[3])
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
    exit "$result"
}
trap finish EXIT
# Ctrl-C goes to the recorder, which closes the bag; the script itself carries on so the EXIT trap
# above can record the result. (A trap, unlike an ignored signal, is reset in child processes.)
trap ':' INT

printf 'Recording all topics to %s\n' "$session_dir/recording"
printf 'Commit: %s | scenario: %s | config files: %s\n' "$commit_sha" "$scenario" "${#copied_configs[@]}"
for ((i = countdown; i > 0; i--)); do
    printf '\rStarting in %2d s ' "$i"
    printf '\a'  # terminal bell, so you can hear it from the mark
    sleep 1
done
((countdown > 0)) && printf '\rRecording now.        \n'
if ((duration > 0)); then
    # SIGINT lets rosbag2 close the bag cleanly; timeout's own 124 means it ran the full time.
    # --foreground keeps the recorder in this process group, so Ctrl-C still stops it early.
    timeout --foreground --signal=INT "$duration" ros2 bag record --all --storage mcap --output "$session_dir/recording" \
        || { code=$?; ((code == 124)) || exit "$code"; }
    printf '\aDone after %s s.\n' "$duration"
else
    ros2 bag record --all --storage mcap --output "$session_dir/recording"
fi
