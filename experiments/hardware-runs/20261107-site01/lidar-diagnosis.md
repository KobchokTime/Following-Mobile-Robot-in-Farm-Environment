# LiDAR Diagnosis — 2026-11-07 Site 01

## Summary

YDLidar **TminiPro** (not X3) on `/dev/ttyUSB0`. Root cause of all prior failures was using
the wrong yaml config (`ydlidar_x3.yaml`). Correct config created at
`/home/yakgreen001/ydlidar_tmini.yaml` and confirmed working. `/scan` publishes at 10.4 Hz.

## Root cause (corrected 10:01)

The driver was launched with `ydlidar_x3.yaml` throughout all prior attempts:

| Wrong param (X3) | Correct (TminiPro) | Effect of wrong value |
|---|---|---|
| `baudrate: 115200` | `baudrate: 230400` | Protocol mismatch — health query happened to respond at 115200 but scan data parse failed |
| `isSingleChannel: true` | `isSingleChannel: false` | Wrong data frame parser → scan data unreadable → timeout loop |
| `support_motor_dtr: true` | `support_motor_dtr: false` | DTR asserted but TminiPro motor is started by scan command, NOT DTR; had no effect |

The LiDAR board itself was never faulty. The motor was not rotating because the driver never
successfully started scan mode with the correct protocol.

## Evidence logs

| File | Created | Config | Result |
|---|---|---|---|
| `lidar_driver.log` | 08:49 | X3 yaml (wrong) | timeout 1,2,1 → Device Failed |
| `lidar4.log` | 09:18 | isSingleChannel:false but other params still X3 | ffffffff health error |
| `lidar5.log` | 09:31 | X3 yaml synchronous run | timeout 1,2,1 → Device Failed |
| `lidar7.log` | 10:00 | **TminiPro yaml (correct)** | **Now lidar is scanning...** ✓ |
| `lidar8.log` | 10:01 | TminiPro yaml, nohup background | Scanning + /scan @ 10.4 Hz ✓ |

## Confirmed working state (10:01)

```
[YDLIDAR] Connection established in [/dev/ttyUSB0][230400]:
Firmware version: 1.0
Hardware version: 2
Model: T-mini Pro
Serial: 2023122000090162
[YDLIDAR] Current scan frequency: 10.00Hz
[YDLIDAR] Lidar init success, Elapsed time 924 ms
[YDLIDAR] Successed to start scan mode, Elapsed time 1938 ms
[YDLIDAR] Fixed Size: 404
[YDLIDAR] Sample Rate: 4.00K
[YDLIDAR] Now lidar is scanning...
```

`ros2 topic hz /scan` → average rate: **10.385 Hz** (window 45)

Sample scan message:
- `frame_id: laser`
- `angle_min/max: ±π` (full 360°)
- `range_min: 0.1 m`, `range_max: 12.0 m`
- Real range values present (e.g. 0.102 m, 0.105 m)

## Correct config: `/home/yakgreen001/ydlidar_tmini.yaml`

```yaml
ydlidar_ros2_driver_node:
  ros__parameters:
    port: /dev/ttyUSB0
    frame_id: laser
    baudrate: 230400
    lidar_type: 1
    device_type: 0
    sample_rate: 4
    isSingleChannel: false
    intensity: false
    support_motor_dtr: false
    frequency: 10.0
    angle_max: 180.0
    angle_min: -180.0
    range_max: 12.0
    range_min: 0.1
    reversion: false
    inverted: false
    auto_reconnect: true
    resolution_fixed: true
    abnormal_check_count: 4
    invalid_range_is_inf: false
```

## Camera status (reference)

Camera `/dev/video0` was running at start of session: PID 19900, 30.5 Hz since 09:02.

## Status

**RESOLVED.** `/scan` topic publishing at 10.4 Hz. Next step: integrate with
person-following pipeline (Priority 3 in EXECUTION_WORKFLOW.md).
