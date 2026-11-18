# Full twin, robot-day configuration

All runs: 107/115 passed, 0 contacts.
Baseline set (22 scenarios x 5 seeds, 6a64669 = 106/110, 0 contacts): 107/110 passed, 0 contacts.

| scenario | passed | contacts | baseline | changed seeds |
| --- | --- | --- | --- | --- |
| blind_corner | 2/5 | 0 | 1/5 | s2 pass (gap 0.535, view 0.904) |
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

- blind_corner s0: gap 2.84 m, view 0.321, fov_end False, contact False
- blind_corner s1: gap 2.831 m, view 0.325, fov_end False, contact False
- blind_corner s4: gap 2.898 m, view 0.465, fov_end True, contact False
- fast_side_step_left s0: gap 4.241 m, view 0.556, fov_end True, contact False
- fast_side_step_left s1: gap 4.208 m, view 0.543, fov_end True, contact False
- fast_side_step_left s2: gap 4.26 m, view 0.583, fov_end True, contact False
- fast_side_step_left s3: gap 4.219 m, view 0.596, fov_end True, contact False
- fast_side_step_left s4: gap 4.208 m, view 0.589, fov_end True, contact False
