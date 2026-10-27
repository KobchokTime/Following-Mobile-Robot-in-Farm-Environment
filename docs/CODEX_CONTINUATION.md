# Codex continuation readiness — 2026-10-27

Prepared at the user's request because Claude is approaching its credit limit. This is a snapshot of
pushed work, not a transfer of the live integration lock or a T14 review verdict. Refresh the refs
before continuing: unpushed work in Claude's cloud session is not visible here.

## Starting state

| Item | Pushed state at preparation |
|---|---|
| `integration-hub` | `ea1fc96`: T14 open, integration lock ready and unowned |
| Merged T14 implementation | `059c549`, from `claude/workspace` `f6035f9` |
| Codex workspace sync | `ad99acc`: hub changes merged into `codex/workspace` |
| Pending Claude patch | `d23e7b2e5787919ffce15299f04247cbacc8b33e` on `claude/robot/box-range`; not in the hub or Claude workspace |
| T13 | Resolved with the stated limits; see `5d8e62e` and [DISCUSSION.md](../DISCUSSION.md) |
| Immediate next work | Review T14 and the pending long-cluster patch before deciding how to continue implementation |

T14 is HANDOFF item 17: give a camera box a LiDAR range from the cluster at its bearing, rather than
the nearest range in a wide sector. The original failure was a same-clothing stranger at 18°, 7.43 m
borrowing the near target's approximately 0.8 m range and entering the normal gate.

The current hub chooses a covering cluster first, otherwise the nearest cluster edge within 5°.
`box_range_from_scan` defaults to true. A fresh scan is at most 0.3 s old. With a fresh scan but no
nearby cluster, the detection is skipped; with no fresh scan, or the parameter false, it uses the old
sector matching. Skipping also bypasses the give-way check for that detection.

## Work that must be preserved

- `d23e7b2` limits the selected cluster's contributing returns to those near the camera bearing, so a
  person chained into a crop-row cluster does not receive the row's minimum range elsewhere.
  It changes `sync_fusion_node.py` and adds
  `test_a_person_against_a_crop_row_gets_the_range_at_the_box` in `test_sector_association.py`.
- This patch has not been merged or independently validated during this preparation. The hub's
  reported 134-test and twin results precede this patch; do not assign those results to it.
- Keep Claude's branches intact. Continue implementation on a Codex-owned feature branch, such as
  `codex/robot/box-range-continuation`, from the refreshed `codex/workspace`. Inspect the pending diff
  and preserve attribution if incorporating its changes.
- `claude/robot/identity-belief` and `claude/robot/static-filter` remain historical experiments, not
  candidates for merging as part of this work.

## Evidence and remaining questions

Read [T14](../DISCUSSION.md), [HANDOFF.md](../HANDOFF.md),
[Claude's log](../logs/claude.md), and the [box-range report](../experiments/sim/2026-10-27_box_range.md)
with its [222-row JSON](../experiments/sim/2026-10-27_box_range.json).

Claude reports, for `445b0e9`: lookalike 20/20 versus old matching 17/20; shade crossing 20/20;
shade side-by-side 10/10; identity 15/15; solo 29/30 with no contact. These are synthetic twin results.
The old matching's shade-crossing seeds 0–9 come from the T13 evidence file; the box-range JSON holds
old-matching seeds 10–19. Recount by condition and seed without double-counting reused runs.

The next reviewer must address all T14 questions:

1. Replay the borrowed-range case through the actual `box_range` and `TargetGate.accept`, with the
   near target and far stranger both represented in the scan. Check that the far box receives its own
   range and is rejected. Keep gate-level results distinct from closed-loop results.
2. Check two-leg geometry across 0.5–3 m, the 5° edge margin, adjacent people's legs, and the long
   crop-row cluster regression. Compare the merged code and `d23e7b2` separately.
3. Check camera bearing, scan direction, `lidar_angle_offset_deg=180`, and any yaw calibration against
   the available configuration. Mounting and leg returns still need robot evidence.
4. Review the fresh-scan/no-cluster skip and give-way behavior, the old-range fallback when the scan
   is stale, and scan/camera time differences up to 0.3 s. Do not silently change these policies.
5. Review duplicated cluster splitting and confirm that fixes do not change target-gate geometry or
   the controller unintentionally. Reply in T14 only after the review; take the HANDOFF lock before
   editing hub coordination files.

## Runtime and run sequence

The local Windows `python` command works. Earlier `python3`/`py -3` aliases did not work reliably.
If a test fails to create a temporary file, set `TEMP` and `TMP` to a writable scratch directory and
rerun. Do not treat a temp-directory permission error as a code assertion failure.

Required offline checks from the repository root:

```text
python -m unittest discover -s tests -p test_sector_association.py
python scripts/check.py
```

Docker, ROS 2 and `rclpy` are unavailable in this local session; WSL previously returned
`E_ACCESSDENIED`. Robot-PC histogram timing remains unmeasured. Video replays additionally need
NumPy, opencv-python-headless and scikit-learn, with `SYNC_FUSION` pointing to the exact reviewed
`sync_fusion_node.py`; the temporary package installation used in the original review was removed.

When a ROS/Docker runner is available, use [sim/README.md](../sim/README.md), run one simulation job
at a time, and give every condition/seed a distinct output directory. Start with `lookalike_after_loss`,
`shade_crossing` and identity `side_by_side`, seeds 0–2, `mps`, realism on, comparing
`box_range_from_scan:=true` and `false`. The container command for one condition is:

```text
python3 -m sim.twin.run_scenario --scenario lookalike_after_loss --bridge-mode mps --seed 0 --realism --ros-param box_range_from_scan:=true --out /repo/sim_runs/t14/box_on/seed0
```

Keep score JSON and state/node logs for failed runs. Cite the tested commit and parameters. A successful
offline test does not establish real camera/LiDAR alignment or a person-identity guarantee.

## Resuming coordination

Fetch first, read the current hub lock and Claude branch tip, and compare them with the snapshot above.
If Claude has published a newer fix, review that state before carrying over `d23e7b2`. Use the existing
Codex worktree, keep the original dirty recovery checkout separate, and append actions to
`logs/codex.md`. HANDOFF and DISCUSSION edits belong on `integration-hub` under its lock. Keep T14
open until its review is complete; authored continuation fixes need an explicitly identified review.

## Preparation checks

On the synced hub code (`ea1fc96`, Codex sync `ad99acc`), `python scripts/check.py` passed all 134
tests with writable temp variables. The local note's links resolve, HANDOFF matches the fetched hub,
and `d23e7b2` remains outside this branch's history. No fresh twin run or T14 verdict was produced
during readiness preparation.
