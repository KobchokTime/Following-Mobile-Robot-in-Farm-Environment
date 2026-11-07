# Block D — On-Ground Speed Check

**Date:** 2026-11-07  
**Site:** site01  
**Condition:** Wheels on ground, no person within 3 m, spotters present

## Bridge params

```
speed_mode:     mps
max_speed_mps:  0.5
wheel_radius_m: 0.085
turn_dir:       1.0
port:           /dev/ttyUSB1
```

## Results

| Speed | Duration | Straight? | Stops cleanly? | Pass |
| --- | --- | --- | --- | --- |
| 0.3 m/s | 2 s | ✅ yes | ✅ yes | ✅ PASS |
| 0.5 m/s | 2 s | ✅ yes | ✅ yes | ✅ PASS |

## Notes

Robot drove straight and stopped cleanly at both test speeds.  
Safety timeout confirmed working on ground (consistent with Block B raised-wheel result).  
Ready to proceed to Block E (perception data recording).
