# Push test 1, 2026-11-15 17:12–17:19. Result: the robot barely moved (user); tracking not tested

The user OK'd this test in chat ("Push test is OK"). Mapping-only bringup: LiDAR + static TFs + slam_toolbox,
no drive bridge, no motor command. The user pushed the robot by hand.

What the data shows:
- Save worked on the growing live map: `live_map_20261115T171845`, 238 × 92 cells, 30.4% known
  (6,661 cells), 596 occupied, received 1.42 s after publication.
- Known cells went 5,732 → 6,679 over 326 s (`push_progress.csv`, 2 s samples) with a steady `/map`
  (age ≤ 2.0 s). The map extent did not change (11.9 × 4.6 m).
- **The robot pose stayed at (0, 0, 0)** in every sample. slam_toolbox added 433 graph nodes, so
  scans were processed (`minimum_travel` 0 works), but they sat at only 2 distinct positions
  ((0, 0) and (0, 0.01)). `map→odom` was the identity at the end.
- At the end, 97% of the current scan points still lay on walls at pose (0, 0). The valid-beam
  count stayed at 303–309 throughout.

Interpretation (to confirm with the user): either the robot hardly moved (for example, the wheels
resisted pushing), or it moved and scan matching never moved the pose. The steady beam count and
the end alignment fit "hardly moved" better, but this run cannot tell the two apart. Map growth
without a pose change can come from small movements or people in view. **Map growth from tracked
motion is still unverified.**

**User's answer (in chat, after the run): "It barely moved."** This fits the data: SLAM correctly
kept the pose at the start, and the small map growth came from small movements or people in view.
The test therefore says nothing about tracking real motion. Scan-only tracking during real motion
is **still unverified**.

Suggested next check, with no robot motion: replay only `/scan` from the 2026-11-15 joystick bag
`20261115T043413Z_slam_map_1115` (3,102 scans and 2,990 `/odom` messages over 299 s, in the PC
backup). Use the mapping-only TFs, `use_sim_time`, and do not replay the bag's `/tf`. Then compare
the SLAM pose path with the bag's wheel `/odom` path.
