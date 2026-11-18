# Full twin, robot-day configuration

All runs: 104/115 passed, 0 contacts.
Baseline set (22 scenarios x 5 seeds, 6a64669 = 106/110, 0 contacts): 104/110 passed, 0 contacts.

| scenario | passed | contacts | baseline | changed seeds |
| --- | --- | --- | --- | --- |
| blind_corner | 0/5 | 0 | 1/5 | s3 FAIL (gap 2.898, view 0.465) |
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
| zigzag | 4/5 | 0 | 5/5 | s4 FAIL (gap 3.841, view 0.247) |

Failed runs:

- blind_corner s0: gap 2.926 m, view 0.465, fov_end True, contact False
- blind_corner s1: gap 2.901 m, view 0.413, fov_end False, contact False
- blind_corner s2: gap 2.871 m, view 0.469, fov_end True, contact False
- blind_corner s3: gap 2.898 m, view 0.465, fov_end False, contact False
- blind_corner s4: gap 0.511 m, view 0.897, fov_end True, contact False
- fast_side_step_left s0: gap 4.226 m, view 0.543, fov_end True, contact False
- fast_side_step_left s1: gap 4.254 m, view 0.576, fov_end True, contact False
- fast_side_step_left s2: gap 4.183 m, view 0.596, fov_end True, contact False
- fast_side_step_left s3: gap 4.212 m, view 0.55, fov_end True, contact False
- fast_side_step_left s4: gap 4.279 m, view 0.576, fov_end True, contact False
- zigzag s4: gap 3.841 m, view 0.247, fov_end False, contact False
