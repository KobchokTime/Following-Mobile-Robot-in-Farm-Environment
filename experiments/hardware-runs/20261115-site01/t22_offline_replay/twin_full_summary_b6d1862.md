# Full twin, robot-day configuration

All runs: 106/115 passed, 0 contacts.
Baseline set (22 scenarios x 5 seeds, 6a64669 = 106/110, 0 contacts): 106/110 passed, 0 contacts.

| scenario | passed | contacts | baseline | changed seeds |
| --- | --- | --- | --- | --- |
| blind_corner | 2/5 | 0 | 1/5 | s1 pass (gap 0.506, view 0.908); s3 FAIL (gap 2.906, view 0.461); s4 pass (gap 0.522, view 0.9) |
| close_pair_same | 5/5 | 0 | 5/5 |  |
| come_back | 5/5 | 0 | 5/5 |  |
| crossing | 5/5 | 0 | 5/5 |  |
| curve_left | 5/5 | 0 | 5/5 |  |
| fast_side_step_left | 0/5 | 0 | new |  |
| head_on | 5/5 | 0 | 5/5 |  |
| lookalike_after_loss | 5/5 | 0 | 5/5 |  |
| pass_by | 4/5 | 0 | 5/5 | s0 FAIL (gap 0.539, view 0.874) |
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

- blind_corner s0: gap 0.518 m, view 0.889, fov_end True, contact False
- blind_corner s2: gap 2.905 m, view 0.465, fov_end True, contact False
- blind_corner s3: gap 2.906 m, view 0.461, fov_end False, contact False
- fast_side_step_left s0: gap 4.208 m, view 0.583, fov_end True, contact False
- fast_side_step_left s1: gap 4.241 m, view 0.589, fov_end True, contact False
- fast_side_step_left s2: gap 4.199 m, view 0.543, fov_end True, contact False
- fast_side_step_left s3: gap 4.194 m, view 0.603, fov_end True, contact False
- fast_side_step_left s4: gap 4.221 m, view 0.543, fov_end True, contact False
- pass_by s0: gap 0.539 m, view 0.874, fov_end True, contact False
