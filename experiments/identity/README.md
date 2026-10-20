# Target identity experiment

This is a measurement protocol, not a claim that target re-identification works.
The example CSV is synthetic. No real crossing/occlusion ground truth has been
collected from the robot yet.

For each frame, assign a stable `target_person_id` using raw video reviewed
independently of the tracker. `selected_person_id` is the ground-truth identity
of the person the robot algorithm selected; leave it empty when the algorithm
abstains. `selected_track_id` is the tracker-assigned ID and must be empty
whenever no person is selected. Frames must be in time order within each run.
Do not derive ground truth from the tracker's own output.

Run `python tools/evaluate_identity.py --input <labeled.csv> --output
<new-metrics.json>`. The evaluator refuses to overwrite prior metrics and
records the input SHA-256. It reports wrong-follow, target coverage, abstention,
track ID changes on consecutive correctly selected frames, and stop/reacquire
delays with censored episodes. Review raw data, clock metadata, code revision,
config, and annotation quality before any result can be called verified.

Use distinct runs for single-person, crossing, similar clothing, partial/full
occlusion, target exit, and re-entry. A run with an absent target must remain in
the dataset; excluding failure or no-target frames would bias the reported metrics.

The separate `replay.example.jsonl` exercises the offline target-lock policy.
Run `python tools/replay_target_identity.py --input
experiments/identity/replay.example.jsonl --output <new-trace.json>` to inspect
the CANDIDATE → LOCKED → LOST transition at a crossing. Its embeddings and
positions are synthetic; the trace is not a real Re-ID benchmark and never
authorizes physical motion.
