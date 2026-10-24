# Role: qa

**Scope (may change):** `tests/`, `scripts/`.

**Responsibilities:** offline tests with ROS and hardware stubs, `scripts/check.py`, and test
coverage for changes made by other roles.

**Rules**
- Never skip, disable or delete a failing test to make a check pass. Fix the cause or report it.
- Tests must run without ROS 2, a camera, LiDAR, motors or network access.
- `scripts/check.py` stays standard-library only, so it runs on both Windows and Linux.

**Done when:** the new behavior is covered, `scripts/check.py` exits 0, and the log entry says
what is still not covered.
