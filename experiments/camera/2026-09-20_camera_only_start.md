# Camera-only restart — 2026-09-20

## Decision

LiDAR is removed from the current critical path because the physical sensor is not available. The motor remains locked. Development continues with the Logitech C922 as the only live sensor.

## Verified baseline

- Camera: Logitech C922 at `/dev/video0`, verified at 640×480.
- Existing PyTorch probes work but are too slow for closed-loop use (multi-second inference).
- Robot already has OpenVINO 2025.2 and Ultralytics in `~/openvino_env`.
- The repository contains a YOLOv8n OpenVINO IR export (`.xml`, `.bin`, metadata).

## Pipeline being built

1. C922 frame capture.
2. YOLOv8n OpenVINO person detection on CPU.
3. Single-target association and temporal tracking.
4. Pose-based orientation classification (front/back/left/right/uncertain).
5. Confidence gate and lost-target state.
6. Motor command generation only after offline and stationary safety tests pass.

## Work completed offline

- Added a fixed-path, allowlisted OpenVINO model deployment endpoint to the local bridge.
- Added a 60-frame OpenVINO benchmark using the real robot camera.
- Added camera ownership locking so stream, snapshot, orientation, and benchmark cannot contend for the camera.
- Added a Camera-only pipeline panel to Robot Console with deployment and benchmark controls.
- Kept all motor writes disabled.

## Acceptance gates

- Detection benchmark: mean ≥10 FPS, report median and P95 latency.
- Target stability: no ID switch in single-person baseline clips.
- Orientation: report confusion matrix over FRONT/BACK/LEFT/RIGHT/NO_TARGET; never force a direction when uncertain.
- Lost target: enter LOST state instead of continuing stale motion.
- Motor output: zero until explicit stationary and emergency-stop checks pass.

## Current blocker

Resolved: the robot was reachable over SSH during the local test. The earlier failure was caused by the local bridge running without LAN permission; a blank password field was present in the browser UI.

## Real camera results

| Test | Result |
|---|---:|
| OpenVINO 640×640, 60 frames | 3.70 FPS; mean 269.9 ms; P95 274.1 ms |
| OpenVINO 320×320, 60 frames | **14.09 FPS**; mean 71.0 ms; P95 71.8 ms |
| Camera capture | mean 0.8 ms |
| No-person tracking safety probe, 80 measured frames | PASS at 13.95 FPS |
| False person detections in empty scene | 0/80 |
| Motor commands during tests | 0 |

The 320×320 OpenVINO export passes the 10 FPS gate and is the selected detector for the camera-only pipeline. A person must be placed in the camera view before measuring acquisition, loss recovery, ID stability, and orientation accuracy.

## Person-present run

- OpenVINO tracking: person detected in 80/80 frames at 14.03 FPS.
- Lost events: 0.
- Motor commands: 0.
- Pose orientation run: `2026-09-20T03-36-06-854Z_9477331a`.
- Prediction: FRONT at 0.79 heuristic confidence; 15/17 visible keypoints; 5138.6 ms.
- Ground truth from the observed scene: LEFT.
- Outcome: orientation **misclassification**. Raw frame, overlay, prediction metadata, and ground-truth record were retained for the confusion matrix.

The detector/tracker is fast enough for the next camera-only stage. The current pose heuristic is not fast or reliable enough for control and must remain advisory/abstaining until replaced or recalibrated.

## Guided four-direction sequence

| Ground truth | Prediction | Confidence | Keypoints | Latency |
|---|---|---:|---:|---:|
| RIGHT | UNCERTAIN | 0.00 | 12/17 | 3936.3 ms |
| BACK | UNCERTAIN | 0.35 | 9/17 | 3912.1 ms |
| FRONT | UNCERTAIN | 0.35 | 9/17 | 3914.8 ms |
| LEFT | FRONT | 0.79 | 12/17 | 3925.9 ms |

Directed-sequence exact accuracy is 0/4. Three cases abstained safely; LEFT was misclassified as FRONT. This confirms that the current face-visible heuristic cannot separate profile views and that the PyTorch pose path is roughly 55× slower than the 320 OpenVINO detector. It must not drive motion.

Recommended next implementation: keep the 14 FPS OpenVINO detector/tracker, replace the single-frame orientation heuristic with a small temporal orientation classifier trained from labeled crops, and retain UNCERTAIN as a mandatory control-blocking state.

## Keypoint-rule revision and visually verified validation

The protocol was corrected so the requested pose is no longer copied into ground truth. Each ground-truth label below was assigned only after visual inspection of the saved raw frame.

| Ground truth | Prediction | Confidence | Face asymmetry | Run |
|---|---|---:|---:|---|
| LEFT | LEFT | 0.79 | +1.4327 | `2026-09-20T04-02-43-471Z_a87448aa` |
| RIGHT | RIGHT | 0.73 | -1.1318 | `2026-09-20T04-08-29-653Z_39231897` |
| FRONT | FRONT | 0.88 | +0.0825 | `2026-09-20T04-14-24-672Z_8c9ea927` |
| BACK | BACK | 0.80 | +0.0513 | `2026-09-20T04-20-54-440Z_989db605` |

This controlled validation is 4/4 correct. It is a development check, not a publication-grade accuracy claim: one verified sample per class is insufficient. The pose path still takes about 3.9 seconds per frame, so it remains unsuitable for direct real-time motor control. The next stage should collect repeated samples under different distances, lighting, clothing, partial occlusion, and intermediate angles, then move the revised features into a faster temporal classifier.

## Persistent pose acceleration

`yolov8n-pose.pt` was exported on the robot as a static 320×320 OpenVINO model. A persistent 30-frame benchmark, excluding five warm-up frames, produced:

- Mean: 92.5 ms
- Median: 92.1 ms
- P95: 95.7 ms
- Throughput: **10.82 FPS**
- Maximum people detected: 1

This is roughly 42× faster than the previous per-request PyTorch path. The remaining engineering change is architectural: keep this model resident, apply temporal voting over recent frames, and expose only the stable orientation state to the controller. Model startup/compilation must not occur inside each control cycle.

## Resident temporal pose service

The architectural change above is now implemented and verified on the robot:

- The OpenVINO pose model is loaded once and kept resident on the robot.
- The service captures `/dev/video0` continuously and applies a 7-frame temporal vote with a minimum of 4 votes.
- It listens only on robot loopback (`127.0.0.1:8765`); Robot Console reads it through the existing SSH bridge.
- End-to-end GUI verification reported stable `LEFT`, instant `LEFT`, and **10.52 FPS**.
- Motor commands remained **0** throughout deployment and verification.

This establishes the real-time advisory orientation path. It is not yet authorized to drive motion. Remaining physical validation gates are repeated multi-condition orientation trials, target-loss transition, reacquisition, and stationary motor-output verification with the wheels lifted.

## Self-guided validation UI

Robot Console now shows the latest annotated pose frame beside a reference illustration and instruction. An automatic sequence runs `FRONT → BACK → LEFT → RIGHT → NO_TARGET`; each stage advances only when the stable temporal output matches continuously for three seconds. A mismatch or `UNCERTAIN` resets the hold timer. Live verification confirmed annotated frames at approximately 8.7–10.8 FPS with motor commands fixed at zero.

The first complete automatic sequence passed all five stages, including the final target-loss transition to stable `NO_TARGET`. A presentation defect reset the final progress bar to 0% even though the completion state and completed-stage list were correct; the UI now retains 100% and displays an explicit PASS banner after completion.

## Next physical gate: loss and reacquisition

The GUI now also prepares a `FRONT → NO_TARGET → FRONT` sequence. It will be the next retained hardware experiment: each state must remain stable for three seconds, the latest annotated frame must be saved, and `motor_commands` must remain zero across disappearance and recovery. This test has been implemented but not yet recorded as a completed run.
