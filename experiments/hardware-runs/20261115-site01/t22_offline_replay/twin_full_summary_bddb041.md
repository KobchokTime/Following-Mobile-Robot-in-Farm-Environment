# Full twin, robot-day configuration

All runs: 108/115 passed, 0 contacts.
Baseline set (22 scenarios x 5 seeds, 6a64669 = 106/110, 0 contacts): 108/110 passed, 0 contacts.

| scenario | passed | contacts | baseline | changed seeds |
| --- | --- | --- | --- | --- |
| blind_corner | 3/5 | 0 | 1/5 | s0 pass (gap 0.526, view 0.904); s4 pass (gap 0.532, view 0.904) |
| close_pair_same | 5/5 | 0 | 5/5 |  |
| come_back | 5/5 | 0 | 5/5 |  |
| crossing | 5/5 | 0 | 5/5 |  |
| curve_left | 5/5 | 0 | 5/5 |  |
| fast_side_step_left | 0/5 | 0 | new |  |
| head_on | 5/5 | 0 | 5/5 |  |
| lookalike_after_loss | 5/5 | 0 | 5/5 |  |
| pass_by | 5/5 | 0 | 5/5 |  |
| shade_crossing | 5/5 | 0 | 5/5 |  |
| shade_side_by_side | 5/5 | 0 | 5/5 |  |
| side_by_side | 5/5 | 0 | 5/5 |  |
| side_by_side_same | 5/5 | 0 | 5/5 |  |
| side_step | 5/5 | 0 | 5/5 |  |
| stand_aside | 5/5 | 0 | 5/5 |  |
| stop_and_go | 5/5 | 0 | 5/5 |  |
| straight | 5/5 | 0 | 5/5 |  |
| target_loss | 5/5 | 0 | 5/5 |  |
| turn_90 | 5/5 | 0 | 5/5 |  |
| walk_0p6 | 5/5 | 0 | 5/5 |  |
| walk_1p0 | 5/5 | 0 | 5/5 |  |
| walk_up_same | 5/5 | 0 | 5/5 |  |
| zigzag | 5/5 | 0 | 5/5 |  |

Failed runs:

- blind_corner s1: gap 0.533 m, view 0.845, fov_end True, contact False
- blind_corner s2: gap 0.532 m, view 0.886, fov_end True, contact False
- fast_side_step_left s0: gap 4.267 m, view 0.556, fov_end True, contact False
- fast_side_step_left s1: gap 4.214 m, view 0.57, fov_end True, contact False
- fast_side_step_left s2: gap 4.212 m, view 0.596, fov_end True, contact False
- fast_side_step_left s3: gap 4.249 m, view 0.596, fov_end True, contact False
- fast_side_step_left s4: gap 4.24 m, view 0.589, fov_end True, contact False
