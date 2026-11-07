# Block C — Full Bringup Preflight

**Date:** 2026-11-07  
**Site:** site01  
**Condition:** Wheels lifted off ground, spotters present

## System state at preflight

| Component | Node | Status |
| --- | --- | --- |
| YDLidar TminiPro | `/ydlidar_ros2_driver_node` | ✅ Running |
| slam_toolbox (online async) | `/slam_toolbox` | ✅ Running |
| Static TF base_link→laser | `/static_transform_publisher` | ✅ Running |
| ZLAC drive bridge | `/zlac_drive_bridge` | ✅ Running |
| joy_node (Logitech RumblePad 2) | `/joy_node` | ✅ Running |
| teleop_twist_joy | `/teleop_twist_joy_node` | ✅ Running |

## Topic rates

| Topic | Expected | Measured | Pass |
| --- | --- | --- | --- |
| `/scan` | ~10 Hz | 10.4 Hz | ✅ |
| `/odom` | ~10 Hz | 9.8 Hz | ✅ |
| `/map` | published after motion | not yet (wheels lifted) | ✅ expected |

## TF chain

```
map → odom          (slam_toolbox)
odom → base_link    (zlac_drive_bridge dead-reckoning)
base_link → laser   (static_transform_publisher, z=0.10 m)
```

Full chain verified: `map → odom → base_link → laser` ✅

## Bridge params (Block C)

```
speed_mode:     mps
max_speed_mps:  0.5
wheel_radius_m: 0.085
turn_dir:       1.0
port:           /dev/ttyUSB1
```

## Result

**PASS** — all nodes running, all topics at expected rates, TF chain complete.  
Ready to proceed to Block D (on-ground speed check) when wheels are lowered.
